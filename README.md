# NHarent — Vergadertranscriptie & Slimme Automatiseringen

Lokale transcriptie van vergaderopnames (m4a) met speaker diarization,
plus AI-gestuurde automatiseringen voor dagelijks taakbeheer via
Microsoft 365 (Outlook, Agenda, To Do).

## Setup

### 1. Vereisten

- macOS met Apple Silicon (M1/M2/M3)
- Python 3.11+
- ffmpeg
- HuggingFace account (voor Pyannote diarization)

```bash
brew install ffmpeg
```

### 2. Installatie

```bash
python3 -m venv .venv
source .venv/bin/activate

# PyTorch met MPS-ondersteuning
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# Dependencies
pip install -r requirements.txt
```

### 3. HuggingFace token (voor diarization)

Ga naar [hf.co/settings/tokens](https://huggingface.co/settings/tokens) en maak een token aan.
Accepteer de gebruiksvoorwaarden van deze modellen:
- [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
- [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)

```bash
export HF_TOKEN="hf_..."
```

### 4. Anthropic API key (optioneel, voor samenvatting)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Gebruik

### Basistranscriptie (zonder diarization)

```bash
python transcribe.py opname.m4a
```

### Met speaker diarization

```bash
python transcribe.py opname.m4a --hf-token $HF_TOKEN
```

### Met samenvatting

```bash
python transcribe.py opname.m4a --hf-token $HF_TOKEN --summarize
```

### Alle opties

```bash
python transcribe.py opname.m4a \
  --model large-v3 \
  --language nl \
  --hf-token $HF_TOKEN \
  --min-speakers 2 \
  --max-speakers 5 \
  --summarize \
  --output vergadering.md \
  --keep-audio \
  --batch-size 4 \
  --verbose
```

| Optie | Omschrijving |
|-------|-------------|
| `--model` | Whisper model: `tiny`, `base`, `small`, `medium`, `large-v3` (default) |
| `--language` | Taal: `nl` (default), `en` |
| `--hf-token` | HuggingFace token voor Pyannote (of `HF_TOKEN` env) |
| `--min-speakers` | Minimum aantal sprekers |
| `--max-speakers` | Maximum aantal sprekers |
| `--summarize` | Voeg AI-samenvatting toe (vereist `ANTHROPIC_API_KEY`) |
| `--output / -o` | Output bestandspad (default: `<input>.md`) |
| `--keep-audio` | Behoud het audiobestand (default: verwijderen na succes) |
| `--batch-size` | Batch size voor transcriptie (default: 8, MPS max 4) |
| `--verbose / -v` | Uitgebreide logging |

## Output

Het script genereert een Markdown-bestand met:

- Transcript gegroepeerd per spreker met timestamps
- (Optioneel) Samenvatting met executive summary, besluiten en actiepunten

## Tips (transcriptie)

- **Kleiner model** (`--model small`) voor snellere transcriptie bij kortere opnames
- **Batch size verlagen** (`--batch-size 2`) als je geheugenproblemen hebt
- **`--max-speakers`** instellen verbetert de diarization-kwaliteit aanzienlijk
- Het eerste gebruik downloadt de modellen (~3 GB voor large-v3)

---

## Slimme Automatiseringen

AI-gestuurde taakextractie en dagelijks taakbeheer. Haalt actiepunten uit
je e-mails, agenda en vergadertranscripties, en pusht ze naar Microsoft To Do.

### Wat het doet

| Bron | Actie |
|------|-------|
| **Outlook e-mail** | Scant ongelezen mails, extraheert actiepunten met AI |
| **Outlook agenda** | Identificeert vergaderingen die voorbereiding nodig hebben |
| **Vergadertranscripties** | Haalt besluiten en actiepunten uit transcripts |
| **Microsoft To Do** | Maakt taken aan met prioriteit en deadline |
| **Dagelijkse briefing** | AI-gegenereerd overzicht van je dag |

### Setup automatiseringen

#### 1. Extra dependencies installeren

```bash
pip install -r requirements.txt
```

#### 2. Microsoft Azure App registreren

1. Ga naar [Azure Portal — App registrations](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade)
2. Klik **New registration**
3. Naam: `NHarent` (of wat je wilt)
4. Supported account types: **Accounts in any organizational directory and personal Microsoft accounts**
5. Redirect URI: **Public client/native** → `http://localhost`
6. Na registratie: kopieer **Application (client) ID** en **Directory (tenant) ID**

#### 3. Environment variables instellen

```bash
export MS_CLIENT_ID="je-client-id-hier"
export MS_TENANT_ID="je-tenant-id-hier"  # of "common" voor persoonlijke accounts
export ANTHROPIC_API_KEY="sk-ant-..."
```

#### 4. Eerste configuratie

```bash
python automations.py setup
```

### Gebruik automatiseringen

#### Volledige dagelijkse run

```bash
python automations.py run
```

Dit doet achtereenvolgens:
1. Scant ongelezen e-mails op actiepunten
2. Analyseert agenda voor voorbereidingen
3. Verwerkt recente vergadertranscripties
4. Prioriteert en dedupliceert met AI
5. Pusht taken naar Microsoft To Do
6. Genereert dagelijkse briefing

#### Individuele commando's

```bash
# Alleen e-mail acties
python automations.py mail

# Alleen agenda acties
python automations.py calendar

# Acties uit een specifiek transcript
python automations.py transcript vergadering.md

# Dagelijkse briefing
python automations.py briefing

# Open taken bekijken
python automations.py status
```

### iPhone synchronisatie

Taken die naar Microsoft To Do worden gepusht, synchroniseren automatisch
naar de **Microsoft To Do** app op je iPhone. Installeer de app uit de App Store
en log in met hetzelfde Microsoft-account.

### Automatisch draaien (optioneel)

Voeg een cron job toe om de automatisering dagelijks te draaien:

```bash
# Elke werkdag om 07:30
crontab -e
30 7 * * 1-5 cd /pad/naar/NHarent && .venv/bin/python automations.py run >> ~/.nharent/automation.log 2>&1
```
