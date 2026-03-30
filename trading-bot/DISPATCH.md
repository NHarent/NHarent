# Claude Dispatch Prompts

## 1. Installatie Prompt (eenmalig)

Kopieer deze prompt naar Claude Code dispatch om de bot te installeren op je MacBook:

```
Installeer de Bitvavo trading bot op dit systeem.

Stappen:
1. Ga naar de trading-bot directory in dit project
2. Maak een Python virtual environment: python3 -m venv .venv
3. Activeer het: source .venv/bin/activate
4. Installeer dependencies: pip install -r requirements.txt
5. Controleer of config.json bestaat. Zo niet, kopieer config.example.json naar config.json
6. Vraag de gebruiker om de Bitvavo API key en secret in te vullen in config.json
7. Test de bot met: python bot.py --config config.json --dry-run --verbose
8. Als de test slaagt, start de status_writer: python status_writer.py --config config.json --output status.json --interval 60
9. Rapporteer het resultaat
```

## 2. Monitor Prompt (scheduled — elke 5-10 min)

Gebruik deze prompt als scheduled trigger om de bot te monitoren:

```
Je bent een trading bot monitor. Lees trading-bot/status.json en analyseer:

1. GEZONDHEID: Draait de bot nog? (check timestamp, >10 min = alarm)
2. WINST: Totaal vermogen vs startkapitaal, winst/verlies %
3. RISICO: Drawdown >5%? Te veel open orders? Verliesreeks?
4. TRADES: Hoeveel vandaag, gemiddelde winst per trade

Als er problemen zijn:
- Bot gestopt → herstart met: cd trading-bot && source .venv/bin/activate && python bot.py --config config.json &
- Verlies >5% → pauzeer de bot en waarschuw
- Geen recente trades → check of grid nog actief is

Houd het rapport kort (max 8 regels). Schrijf in het Nederlands.
```

## 3. Dagelijks Rapport Prompt (scheduled — 1x per dag)

```
Maak een dagelijks rapport van de trading bot.

1. Lees trading-bot/status.json voor huidige status
2. Lees trading-bot/trading-bot.log voor vandaag's activiteit
3. Bereken:
   - Totale winst/verlies vandaag
   - Aantal trades
   - Beste en slechtste trade
   - Gemiddelde spread-winst
4. Vergelijk met gisteren (als er history is)
5. Geef een aanbeveling: doorgaan, grid aanpassen, of pauzeren

Schrijf een kort maar informatief rapport in het Nederlands.
```

## Hoe te gebruiken

### Via Claude Code CLI:

```bash
# Eenmalig installeren
claude --prompt "$(cat DISPATCH.md | sed -n '/^1\. Installatie/,/^```$/p')"

# Of handmatig de prompt kopiëren en plakken in Claude Code
```

### Via Claude Code scheduled triggers:

```bash
# Monitor elke 10 minuten
claude schedule create \
  --name "trading-bot-monitor" \
  --cron "*/10 * * * *" \
  --prompt "$(cat <<'EOF'
Je bent een trading bot monitor. Lees trading-bot/status.json en analyseer:
1. GEZONDHEID: Draait de bot nog? (check timestamp, >10 min = alarm)
2. WINST: Totaal vermogen vs startkapitaal, winst/verlies %
3. RISICO: Drawdown >5%? Te veel open orders?
4. TRADES: Hoeveel vandaag, gemiddelde winst per trade
Houd het kort (max 8 regels). Nederlands.
EOF
)"

# Dagelijks rapport om 20:00
claude schedule create \
  --name "trading-bot-dagrapport" \
  --cron "0 20 * * *" \
  --prompt "Maak een dagelijks rapport van de trading bot. Lees status.json en trading-bot.log. Rapporteer winst, trades, risico. Nederlands."
```
