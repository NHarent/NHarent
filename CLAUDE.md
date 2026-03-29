# CLAUDE.md

## Project Overview

Personal utility repository with two standalone tools for Dutch-speaking users:

1. **`transcribe.py`** — CLI tool that transcribes meeting recordings (m4a) to Markdown with speaker diarization, optimized for macOS Apple Silicon
2. **`image-tool.html`** — Browser-based drag-and-drop tool that converts images to base64 HTML embeds

## Repository Structure

```
├── transcribe.py        # Python CLI — meeting transcription + diarization
├── image-tool.html      # Standalone HTML/JS — image to base64 converter
├── requirements.txt     # Python dependencies
└── README.md            # Setup & usage docs (Dutch)
```

## Tech Stack

- **Python 3.11+** with WhisperX, Pyannote, PyTorch (MPS/CPU), Click, Anthropic SDK
- **Vanilla HTML/CSS/JS** (no build tools, no framework)
- **No CI/CD, no tests, no linter configs**

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

Required env vars:
- `HF_TOKEN` — HuggingFace token for Pyannote diarization models
- `ANTHROPIC_API_KEY` — (optional) for AI-powered meeting summaries

## Code Conventions

- **Language**: All comments, docstrings, UI text, and documentation are in **Dutch**
- **Python style**: snake_case functions/variables, section separators with `# ---` comment blocks, modular function design
- **CLI**: Click decorators with env var fallbacks for secrets
- **HTML tool**: Single self-contained file, no external dependencies, inline CSS and JS
- **No formal linting or formatting** rules are enforced

## Key Architecture Decisions

- Pyannote diarization runs on CPU even when MPS is available (stability)
- MPS batch size is capped at 4 to prevent memory issues
- Models are deleted after use and MPS cache is cleared explicitly
- Audio files are deleted after successful transcription by default (`--keep-audio` to preserve)
- Anthropic SDK import is deferred (only imported when `--summarize` is used)

## When Modifying This Project

- Keep tools self-contained — `image-tool.html` must remain a single file with no external deps
- Maintain Dutch language for all user-facing text, comments, and documentation
- Test MPS and CPU code paths when changing `transcribe.py`
- Do not add build systems, bundlers, or package managers for the HTML tool
- Keep `requirements.txt` minimal — only add dependencies that are actually needed
