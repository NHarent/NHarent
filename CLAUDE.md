# NHarent - Personal Tools

## Project Overview
A collection of personal developer tools:
- **transcribe.py** - Local meeting transcription (macOS Apple Silicon) using WhisperX + Pyannote speaker diarization, optional summarization via Anthropic API
- **image-tool.html** - Browser-based image-to-HTML embed converter (standalone, no build step)

## Language
- Code comments and UI: Dutch (Nederlands)
- Variable names and code: English

## Tech Stack
- Python 3.11+ with Click CLI framework
- WhisperX for transcription, Pyannote for speaker diarization
- PyTorch with MPS (Apple Silicon) support
- Anthropic SDK for optional AI summarization

## Development
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Key Notes
- transcribe.py targets macOS Apple Silicon (MPS device); falls back to CPU
- Audio files are deleted after successful transcription by default (use --keep-audio to preserve)
- HuggingFace token required for diarization features
- image-tool.html is fully self-contained (no dependencies, no build)
