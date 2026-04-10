# Claude Instructies

## Taal & Communicatie

- Communiceer altijd in het **Nederlands**
- Code comments en docstrings in het Nederlands
- Variabelen, functies en technische termen mogen Engels zijn (Python conventie)
- Foutmeldingen en CLI-output in het Nederlands
- Wees direct en bondig — geen overbodige uitleg

## Codestijl

- **Python 3.11+** met moderne syntax: `str | None` (geen `Optional`), `list[dict]` (geen `List[Dict]`)
- Type hints op alle functies
- Docstrings in het Nederlands (korte omschrijving, geen uitgebreide Google/NumPy style)
- Gebruik `logging` module met Nederlandse logberichten
- Secties in bestanden scheiden met commentaarblokken: `# --- Sectienaam ---`
- `pathlib.Path` boven `os.path`
- f-strings boven `.format()` of `%`
- Imports gegroepeerd: stdlib, third-party, lokaal

## Architectuur & Aanpak

- **Eenvoud eerst**: zelfstandige single-file tools boven complexe projectstructuren
- Geen onnodige abstracties, classes, of design patterns — schrijf alleen wat nodig is
- CLI tools met `click` framework
- Lokale verwerking en privacy waar mogelijk — vermijd cloud-afhankelijkheden tenzij expliciet gevraagd
- Apple Silicon (MPS) ondersteuning met CPU fallback bij GPU-code
- Geheugenoptimalisatie: cache opruimen, batch sizes beperken op MPS

## Technische stack

- **Python**: click, pathlib, logging, torch, anthropic SDK
- **Frontend**: vanilla HTML/CSS/JS — geen frameworks tenzij expliciet gevraagd
- **AI/ML**: WhisperX, Pyannote, Anthropic Claude API
- **Platform**: macOS Apple Silicon primair, cross-platform als bonus
- Gebruik altijd het nieuwste Claude model (`claude-sonnet-4-20250514` of nieuwer) bij Anthropic API calls

## Documentatie

- README.md in het Nederlands
- Bevat: doel, setup-instructies, gebruiksvoorbeelden, alle CLI-opties in een tabel
- Troubleshooting/tips sectie waar relevant
- Geen overbodige badges, shields, of boilerplate

## Wat NIET te doen

- Geen Engels praten tenzij expliciet gevraagd
- Geen onnodige error handling voor scenario's die niet voorkomen
- Geen extra bestanden aanmaken (utils.py, config.py, etc.) tenzij echt nodig
- Geen docstring-stijl wijzigen in bestaande code
- Geen frameworks of dependencies toevoegen zonder goede reden
- Geen `.env` bestanden aanmaken — gebruik environment variables direct
