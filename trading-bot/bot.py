#!/usr/bin/env python3
"""
Bitvavo Grid Trading Bot — 24/7 automatisch handelen
Conservatieve grid-strategie ontworpen voor klein startkapitaal (€100).

Strategieën:
  grid  — Plaatst koop/verkoop orders op vaste prijsniveaus (grid).
           Verdient aan de spread bij zijwaartse markten.
  dca   — Dollar Cost Averaging: koopt periodiek een vast bedrag.
           Laagste risico, bouwt positie op over tijd.

Gebruik:
  python bot.py --config config.json
  python bot.py --config config.json --strategy dca
  python bot.py --config config.json --dry-run        # Simulatie zonder echt geld
"""

import argparse
import json
import logging
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    from python_bitvavo_api.bitvavo import Bitvavo
except ImportError:
    print("Installeer eerst: pip install python-bitvavo-api")
    sys.exit(1)

import requests

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(log_file: str, verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger("trading-bot")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("[%(asctime)s] %(levelname)-8s %(message)s", "%Y-%m-%d %H:%M:%S")

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


# ---------------------------------------------------------------------------
# Telegram notificaties
# ---------------------------------------------------------------------------

def send_telegram(token: str, chat_id: str, message: str):
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Exchange wrapper
# ---------------------------------------------------------------------------

class Exchange:
    """Wrapper rond Bitvavo API met dry-run ondersteuning."""

    def __init__(self, config: dict, dry_run: bool = False, logger: logging.Logger = None):
        self.dry_run = dry_run
        self.log = logger or logging.getLogger("trading-bot")
        self.pair = config["pair"]
        self.config = config

        if dry_run:
            self.log.info("=== DRY RUN MODUS — geen echte orders ===")
            self.bitvavo = Bitvavo({
                "APIKEY": config.get("api_key", ""),
                "APISECRET": config.get("api_secret", ""),
                "RESTURL": "https://api.bitvavo.com/v2",
                "WSURL": "wss://ws.bitvavo.com/v2/",
                "ACCESSWINDOW": 10000,
                "DEBUGGING": False,
            })
        else:
            self.bitvavo = Bitvavo({
                "APIKEY": config["api_key"],
                "APISECRET": config["api_secret"],
                "RESTURL": "https://api.bitvavo.com/v2",
                "WSURL": "wss://ws.bitvavo.com/v2/",
                "ACCESSWINDOW": 10000,
                "DEBUGGING": False,
            })

    def get_price(self) -> float:
        ticker = self.bitvavo.tickerPrice({"market": self.pair})
        if "price" in ticker:
            return float(ticker["price"])
        if isinstance(ticker, list) and len(ticker) > 0:
            return float(ticker[0]["price"])
        raise ValueError(f"Kan prijs niet ophalen: {ticker}")

    def get_balance(self, asset: str) -> float:
        if self.dry_run:
            return self.config.get("capital", 100)
        balances = self.bitvavo.balance({"symbol": asset})
        if isinstance(balances, list) and len(balances) > 0:
            return float(balances[0].get("available", 0))
        if isinstance(balances, dict) and "available" in balances:
            return float(balances["available"])
        return 0.0

    def place_buy(self, amount_eur: float, price: float = None) -> dict:
        base, quote = self.pair.split("-")
        if price:
            order = {
                "market": self.pair,
                "side": "buy",
                "orderType": "limit",
                "price": f"{price:.2f}",
                "amountQuote": f"{amount_eur:.2f}",
            }
        else:
            order = {
                "market": self.pair,
                "side": "buy",
                "orderType": "market",
                "amountQuote": f"{amount_eur:.2f}",
            }

        if self.dry_run:
            self.log.info(f"[DRY RUN] KOOP €{amount_eur:.2f} {base} @ {'markt' if not price else f'€{price:.2f}'}")
            return {"orderId": "dry-run", "status": "simulated"}

        result = self.bitvavo.placeOrder(self.pair, "buy", order["orderType"],
                                          {k: v for k, v in order.items()
                                           if k not in ("market", "side", "orderType")})
        self.log.info(f"KOOP order geplaatst: €{amount_eur:.2f} — {result}")
        return result

    def place_sell(self, amount_asset: float, price: float = None) -> dict:
        base, quote = self.pair.split("-")
        if price:
            order_type = "limit"
            body = {"price": f"{price:.2f}", "amount": f"{amount_asset:.8f}"}
        else:
            order_type = "market"
            body = {"amount": f"{amount_asset:.8f}"}

        if self.dry_run:
            self.log.info(f"[DRY RUN] VERKOOP {amount_asset:.8f} {base} @ {'markt' if not price else f'€{price:.2f}'}")
            return {"orderId": "dry-run", "status": "simulated"}

        result = self.bitvavo.placeOrder(self.pair, "sell", order_type, body)
        self.log.info(f"VERKOOP order geplaatst: {amount_asset:.8f} {base} — {result}")
        return result

    def get_open_orders(self) -> list:
        if self.dry_run:
            return []
        return self.bitvavo.ordersOpen({"market": self.pair})

    def cancel_all_orders(self):
        if self.dry_run:
            return
        orders = self.get_open_orders()
        for order in orders:
            self.bitvavo.cancelOrder(self.pair, order["orderId"])
            self.log.info(f"Order geannuleerd: {order['orderId']}")

    def get_trades(self, limit: int = 50) -> list:
        if self.dry_run:
            return []
        return self.bitvavo.trades(self.pair, {"limit": limit})


# ---------------------------------------------------------------------------
# Grid Trading Strategie
# ---------------------------------------------------------------------------

class GridStrategy:
    """
    Plaatst koop-orders onder de huidige prijs en verkoop-orders erboven.
    Wanneer een koop-order wordt gevuld, plaatst het een verkoop-order op het
    niveau erboven (en vice versa). Verdient aan de spread.
    """

    def __init__(self, exchange: Exchange, config: dict, logger: logging.Logger):
        self.exchange = exchange
        self.log = logger
        self.pair = config["pair"]
        self.grid_cfg = config["grid"]
        self.safety = config["safety"]
        self.levels = self.grid_cfg["levels"]
        self.spacing = self.grid_cfg["spacing_percent"] / 100
        self.order_size = self.grid_cfg["order_size_eur"]
        self.daily_trades = 0
        self.daily_reset = datetime.now()
        self.loss_streak = 0
        self.active_grid = {}  # price_level -> order_info

    def calculate_grid_levels(self, current_price: float) -> dict:
        """Bereken grid niveaus rond de huidige prijs."""
        levels = {}
        half = self.levels // 2

        for i in range(-half, half + 1):
            if i == 0:
                continue
            price = current_price * (1 + i * self.spacing)
            side = "buy" if i < 0 else "sell"
            levels[round(price, 2)] = side

        return levels

    def setup_grid(self):
        """Plaats initiële grid orders."""
        price = self.exchange.get_price()
        self.log.info(f"Huidige prijs {self.pair}: €{price:.2f}")

        levels = self.calculate_grid_levels(price)
        self.log.info(f"Grid niveaus ({len(levels)}): {json.dumps({str(k): v for k, v in sorted(levels.items())})}")

        # Annuleer bestaande orders
        self.exchange.cancel_all_orders()
        self.active_grid = {}

        base, _ = self.pair.split("-")
        base_balance = self.exchange.get_balance(base)

        for level_price, side in sorted(levels.items()):
            if side == "buy":
                result = self.exchange.place_buy(self.order_size, price=level_price)
                self.active_grid[level_price] = {"side": "buy", "order": result}
            else:
                # Bereken hoeveel asset we kunnen verkopen op dit niveau
                asset_amount = self.order_size / level_price
                if base_balance >= asset_amount or self.exchange.dry_run:
                    result = self.exchange.place_sell(asset_amount, price=level_price)
                    self.active_grid[level_price] = {"side": "sell", "order": result}
                    base_balance -= asset_amount
                else:
                    self.log.warning(f"Onvoldoende {base} voor verkoop @ €{level_price:.2f}")

    def check_and_refresh(self):
        """Controleer gevulde orders en herplaats tegenorders."""
        if datetime.now() - self.daily_reset > timedelta(days=1):
            self.daily_trades = 0
            self.daily_reset = datetime.now()

        if self.daily_trades >= self.safety["max_daily_trades"]:
            self.log.warning("Dagelijks trade-limiet bereikt, wachten...")
            return

        if self.loss_streak >= self.safety["pause_after_loss_streak"]:
            self.log.warning(f"Verliesreeks van {self.loss_streak} — bot gepauzeerd. Herstart handmatig.")
            return

        open_orders = self.exchange.get_open_orders()
        open_ids = {o.get("orderId") for o in open_orders}

        current_price = self.exchange.get_price()

        # Stop-loss check
        for level_price, info in list(self.active_grid.items()):
            if info["side"] == "buy":
                drop = (level_price - current_price) / level_price * 100
                if drop > self.safety["stop_loss_percent"]:
                    self.log.warning(f"STOP-LOSS: prijs €{current_price:.2f} is {drop:.1f}% onder grid. Grid wordt herplaatst.")
                    self.setup_grid()
                    return

        # Check of orders gevuld zijn
        for level_price, info in list(self.active_grid.items()):
            order_id = info.get("order", {}).get("orderId")
            if order_id and order_id not in open_ids and order_id != "dry-run":
                self.log.info(f"Order gevuld @ €{level_price:.2f} ({info['side']})")
                self.daily_trades += 1

                # Plaats tegenorder
                if info["side"] == "buy":
                    sell_price = level_price * (1 + self.spacing)
                    asset_amount = self.order_size / level_price
                    result = self.exchange.place_sell(asset_amount, price=round(sell_price, 2))
                    self.active_grid[round(sell_price, 2)] = {"side": "sell", "order": result}
                else:
                    buy_price = level_price * (1 - self.spacing)
                    result = self.exchange.place_buy(self.order_size, price=round(buy_price, 2))
                    self.active_grid[round(buy_price, 2)] = {"side": "buy", "order": result}

                del self.active_grid[level_price]

    def run_cycle(self):
        """Eén check-cyclus."""
        try:
            self.check_and_refresh()
        except Exception as e:
            self.log.error(f"Grid cycle fout: {e}")


# ---------------------------------------------------------------------------
# DCA Strategie
# ---------------------------------------------------------------------------

class DCAStrategy:
    """
    Dollar Cost Averaging — koopt periodiek een vast bedrag.
    De veiligste geautomatiseerde strategie.
    """

    def __init__(self, exchange: Exchange, config: dict, logger: logging.Logger):
        self.exchange = exchange
        self.log = logger
        self.interval_hours = config["dca"]["interval_hours"]
        self.amount = config["dca"]["amount_eur"]
        self.last_buy = None

    def run_cycle(self):
        now = datetime.now()

        if self.last_buy and (now - self.last_buy) < timedelta(hours=self.interval_hours):
            remaining = timedelta(hours=self.interval_hours) - (now - self.last_buy)
            self.log.debug(f"DCA: volgende koop over {remaining}")
            return

        try:
            price = self.exchange.get_price()
            self.log.info(f"DCA koop: €{self.amount:.2f} @ €{price:.2f}")
            self.exchange.place_buy(self.amount)
            self.last_buy = now
        except Exception as e:
            self.log.error(f"DCA koop mislukt: {e}")


# ---------------------------------------------------------------------------
# Portfolio tracker
# ---------------------------------------------------------------------------

def show_status(exchange: Exchange, config: dict, logger: logging.Logger):
    """Toon huidige portfolio status."""
    base, quote = config["pair"].split("-")
    try:
        price = exchange.get_price()
        eur_balance = exchange.get_balance(quote)
        asset_balance = exchange.get_balance(base)
        total = eur_balance + (asset_balance * price)
        profit = total - config["capital"]
        profit_pct = (profit / config["capital"]) * 100 if config["capital"] > 0 else 0

        logger.info("=" * 50)
        logger.info(f"  Markt:       {config['pair']} @ €{price:.2f}")
        logger.info(f"  EUR:         €{eur_balance:.2f}")
        logger.info(f"  {base}:       {asset_balance:.8f} (€{asset_balance * price:.2f})")
        logger.info(f"  Totaal:      €{total:.2f}")
        logger.info(f"  Winst/verlies: €{profit:+.2f} ({profit_pct:+.1f}%)")
        logger.info(f"  Open orders: {len(exchange.get_open_orders())}")
        logger.info("=" * 50)
    except Exception as e:
        logger.error(f"Status ophalen mislukt: {e}")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Bitvavo Trading Bot")
    parser.add_argument("--config", "-c", required=True, help="Pad naar config.json")
    parser.add_argument("--strategy", "-s", choices=["grid", "dca"], help="Overschrijf strategie uit config")
    parser.add_argument("--dry-run", "-d", action="store_true", help="Simulatie zonder echte orders")
    parser.add_argument("--verbose", "-v", action="store_true", help="Uitgebreide logging")
    parser.add_argument("--interval", "-i", type=int, default=30, help="Check interval in seconden (default: 30)")
    args = parser.parse_args()

    # Laad configuratie
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config niet gevonden: {config_path}")
        print("Kopieer config.example.json naar config.json en vul je API keys in.")
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    strategy_name = args.strategy or config.get("strategy", "grid")
    logger = setup_logging(config.get("log_file", ""), args.verbose)
    logger.info(f"Trading Bot gestart — strategie: {strategy_name}, pair: {config['pair']}")

    # Telegram notificatie helper
    notif = config.get("notifications", {})
    def notify(msg):
        send_telegram(notif.get("telegram_token", ""), notif.get("telegram_chat_id", ""), msg)

    # Exchange setup
    exchange = Exchange(config, dry_run=args.dry_run, logger=logger)

    # Strategie setup
    if strategy_name == "grid":
        strategy = GridStrategy(exchange, config, logger)
        strategy.setup_grid()
    elif strategy_name == "dca":
        strategy = DCAStrategy(exchange, config, logger)
    else:
        logger.error(f"Onbekende strategie: {strategy_name}")
        sys.exit(1)

    notify(f"Trading Bot gestart\nStrategie: {strategy_name}\nPair: {config['pair']}\nKapitaal: €{config['capital']}")

    # Graceful shutdown
    running = True
    def signal_handler(sig, frame):
        nonlocal running
        logger.info("Shutdown signaal ontvangen...")
        running = False
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Main loop
    status_interval = 300  # Status elke 5 minuten
    last_status = 0
    cycle = 0

    while running:
        try:
            strategy.run_cycle()
            cycle += 1

            if time.time() - last_status > status_interval:
                show_status(exchange, config, logger)
                last_status = time.time()

            time.sleep(args.interval)

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Onverwachte fout: {e}")
            notify(f"BOT FOUT: {e}")
            time.sleep(60)  # Wacht 1 minuut bij fout

    # Cleanup
    logger.info("Bot wordt gestopt...")
    if strategy_name == "grid" and not args.dry_run:
        logger.info("Open orders worden geannuleerd...")
        exchange.cancel_all_orders()

    show_status(exchange, config, logger)
    notify("Trading Bot gestopt.")
    logger.info("Bot gestopt.")


if __name__ == "__main__":
    main()
