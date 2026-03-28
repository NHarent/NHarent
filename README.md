# Vergadertranscriptie (macOS Apple Silicon)

Lokale transcriptie van vergaderopnames (m4a) met speaker diarization.

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

## Tips

- **Kleiner model** (`--model small`) voor snellere transcriptie bij kortere opnames
- **Batch size verlagen** (`--batch-size 2`) als je geheugenproblemen hebt
- **`--max-speakers`** instellen verbetert de diarization-kwaliteit aanzienlijk
- Het eerste gebruik downloadt de modellen (~3 GB voor large-v3)
