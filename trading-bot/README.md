# Bitvavo Trading Bot

Geautomatiseerde 24/7 trading bot voor Bitvavo met conservatieve strategieën, ontworpen voor klein startkapitaal (€100).

## Strategieën

| Strategie | Risico | Hoe het werkt |
|-----------|--------|---------------|
| **Grid** | Laag-midden | Plaatst koop/verkoop orders op vaste prijsniveaus. Verdient aan de spread in zijwaartse markten. |
| **DCA** | Laag | Koopt periodiek een vast bedrag. Bouwt langzaam een positie op tegen gemiddelde prijs. |

## Veiligheidsmaatregelen

- Stop-loss per grid (standaard 5%)
- Maximum dagelijkse trades limiet
- Automatische pauze na verliesreeks
- Maximum open orders limiet
- Dry-run modus om te testen zonder echt geld

## Snel starten

### 1. Installatie

```bash
cd trading-bot
pip install -r requirements.txt
```

### 2. Bitvavo API key aanmaken

1. Ga naar [Bitvavo](https://account.bitvavo.com/user/api) → API keys
2. Maak een nieuwe key aan met:
   - **Trading** rechten: Aan
   - **Withdrawal** rechten: **Uit** (nooit nodig!)
   - IP whitelist: je eigen IP (aanbevolen)
3. Kopieer de key en secret

### 3. Configuratie

```bash
cp config.example.json config.json
# Vul je API key en secret in
```

Pas aan wat je wilt:
- `pair` — Welk handelspaar (BTC-EUR, ETH-EUR, etc.)
- `capital` — Je startkapitaal
- `grid.levels` — Aantal grid niveaus (meer = meer orders)
- `grid.spacing_percent` — Afstand tussen niveaus (groter = minder trades, meer winst per trade)
- `grid.order_size_eur` — Bedrag per order

### 4. Eerst testen (dry-run)

```bash
python bot.py --config config.json --dry-run --verbose
```

Dit simuleert de bot zonder echt geld te gebruiken. Check de logs om te zien of het werkt.

### 5. Live draaien

```bash
# Grid strategie (standaard)
python bot.py --config config.json

# DCA strategie
python bot.py --config config.json --strategy dca

# Met snellere checks (elke 10 seconden)
python bot.py --config config.json --interval 10
```

### 6. 24/7 draaien (achtergrond)

Met `systemd` (Linux):

```bash
# Maak service file
sudo tee /etc/systemd/system/trading-bot.service << 'EOF'
[Unit]
Description=Bitvavo Trading Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/pad/naar/trading-bot
ExecStart=/usr/bin/python3 bot.py --config config.json
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable trading-bot
sudo systemctl start trading-bot
sudo systemctl status trading-bot    # Check status
journalctl -u trading-bot -f         # Volg logs
```

Of simpel met `screen`/`tmux`:

```bash
screen -S tradingbot
python bot.py --config config.json
# Druk Ctrl+A, D om te detachen
# screen -r tradingbot om terug te gaan
```

## Telegram meldingen (optioneel)

1. Maak een bot via [@BotFather](https://t.me/BotFather) op Telegram
2. Stuur `/start` naar je bot
3. Haal je chat ID op via `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Vul `telegram_token` en `telegram_chat_id` in config.json in

## Configuratie-opties

| Optie | Standaard | Beschrijving |
|-------|-----------|-------------|
| `pair` | BTC-EUR | Handelspaar |
| `capital` | 100 | Startkapitaal in EUR |
| `max_risk_percent` | 2 | Max risico per trade |
| `grid.levels` | 5 | Aantal grid niveaus |
| `grid.spacing_percent` | 1.5 | Afstand tussen niveaus |
| `grid.order_size_eur` | 20 | EUR per order |
| `dca.interval_hours` | 24 | Uren tussen DCA aankopen |
| `dca.amount_eur` | 5 | EUR per DCA aankoop |
| `safety.stop_loss_percent` | 5 | Stop-loss percentage |
| `safety.max_daily_trades` | 20 | Max trades per dag |
| `safety.pause_after_loss_streak` | 3 | Pauze na X verliezen op rij |

## Aanbevolen instellingen voor €100

```json
{
  "pair": "BTC-EUR",
  "capital": 100,
  "strategy": "grid",
  "grid": {
    "levels": 5,
    "spacing_percent": 1.5,
    "order_size_eur": 20
  },
  "safety": {
    "stop_loss_percent": 5,
    "max_daily_trades": 20,
    "pause_after_loss_streak": 3
  }
}
```

## Waarschuwing

> **Dit is geen financieel advies.** Handelen in crypto brengt risico's met zich mee.
> Je kunt (een deel van) je inleg verliezen. Test altijd eerst met dry-run modus.
> Begin klein en verhoog alleen als je begrijpt hoe de bot werkt.
