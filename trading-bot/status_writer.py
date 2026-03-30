#!/usr/bin/env python3
"""
Status reporter — schrijft bot-status naar een JSON file die het dashboard leest.
Draait naast de bot op je MacBook.

Gebruik:
  python status_writer.py --config config.json --output status.json --interval 60
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from python_bitvavo_api.bitvavo import Bitvavo


def get_status(config: dict) -> dict:
    bitvavo = Bitvavo({
        "APIKEY": config["api_key"],
        "APISECRET": config["api_secret"],
        "RESTURL": "https://api.bitvavo.com/v2",
        "WSURL": "wss://ws.bitvavo.com/v2/",
        "ACCESSWINDOW": 10000,
        "DEBUGGING": False,
    })

    pair = config["pair"]
    base, quote = pair.split("-")

    ticker = bitvavo.tickerPrice({"market": pair})
    price = float(ticker["price"]) if "price" in ticker else float(ticker[0]["price"])

    eur_bal = bitvavo.balance({"symbol": quote})
    eur = float(eur_bal[0]["available"]) if isinstance(eur_bal, list) and eur_bal else 0

    asset_bal = bitvavo.balance({"symbol": base})
    asset = float(asset_bal[0]["available"]) if isinstance(asset_bal, list) and asset_bal else 0

    open_orders = bitvavo.ordersOpen({"market": pair})
    trades = bitvavo.trades(pair, {"limit": 20})

    total = eur + (asset * price)
    profit = total - config["capital"]
    profit_pct = (profit / config["capital"]) * 100 if config["capital"] > 0 else 0

    # Bereken winst vandaag
    today = datetime.now().strftime("%Y-%m-%d")
    today_trades = [t for t in trades if t.get("timestamp", 0) >
                    datetime.strptime(today, "%Y-%m-%d").timestamp() * 1000]

    recent = []
    for t in trades[:10]:
        ts = datetime.fromtimestamp(t.get("timestamp", 0) / 1000).strftime("%H:%M:%S")
        recent.append({
            "time": ts,
            "side": t.get("side", "?"),
            "amount": t.get("amount", "0"),
            "price": t.get("price", "0"),
            "fee": t.get("fee", "0"),
        })

    return {
        "timestamp": datetime.now().isoformat(),
        "pair": pair,
        "price": round(price, 2),
        "balance_eur": round(eur, 2),
        "balance_asset": round(asset, 8),
        "balance_asset_eur": round(asset * price, 2),
        "total_eur": round(total, 2),
        "capital": config["capital"],
        "profit_eur": round(profit, 2),
        "profit_pct": round(profit_pct, 2),
        "open_orders": len(open_orders) if isinstance(open_orders, list) else 0,
        "trades_today": len(today_trades),
        "recent_trades": recent,
        "strategy": config.get("strategy", "grid"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", "-c", required=True)
    parser.add_argument("--output", "-o", default="status.json")
    parser.add_argument("--interval", "-i", type=int, default=60)
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    print(f"Status writer gestart — elke {args.interval}s naar {args.output}")
    while True:
        try:
            status = get_status(config)
            with open(args.output, "w") as f:
                json.dump(status, f, indent=2)
            print(f"[{status['timestamp']}] €{status['total_eur']} ({status['profit_pct']:+.1f}%)")
        except Exception as e:
            print(f"Fout: {e}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
