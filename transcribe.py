#!/usr/bin/env python3
"""
Lokale vergadertranscriptie voor macOS (Apple Silicon).

Leest m4a-bestanden in, transcribeert met WhisperX (MPS/CPU),
voert speaker diarization uit via Pyannote, en schrijft een
diarized Markdown-transcript. Optioneel: samenvatting via Anthropic API.
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

import click
import torch
import whisperx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Device detection
# ---------------------------------------------------------------------------

def get_device() -> str:
    """Kies MPS (Apple Silicon) als beschikbaar, anders CPU."""
    if torch.backends.mps.is_available():
        logger.info("Gebruik MPS (Apple Silicon GPU)")
        return "mps"
    logger.info("MPS niet beschikbaar — fallback naar CPU")
    return "cpu"


def get_compute_type(device: str) -> str:
    """Kies compute type passend bij device."""
    if device == "mps":
        return "float16"
    return "int8"


# ---------------------------------------------------------------------------
# Transcriptie
# ---------------------------------------------------------------------------

def transcribe_audio(
    audio_path: str,
    model_size: str = "large-v3",
    language: str = "nl",
    device: str | None = None,
    batch_size: int = 8,
) -> tuple[dict, any]:
    """Transcribeer audiobestand met WhisperX."""
    if device is None:
        device = get_device()
    compute_type = get_compute_type(device)

    # MPS heeft kleinere batch nodig om geheugen te sparen
    if device == "mps" and batch_size > 4:
        batch_size = 4

    logger.info(
        "Laden model %s op %s (compute_type=%s, batch_size=%d)",
        model_size, device, compute_type, batch_size,
    )
    model = whisperx.load_model(
        model_size,
        device=device,
        compute_type=compute_type,
        language=language,
    )

    logger.info("Laden audio: %s", audio_path)
    audio = whisperx.load_audio(audio_path)

    logger.info("Transcriberen...")
    result = model.transcribe(audio, batch_size=batch_size, language=language)

    # Alignment voor betere timestamps
    logger.info("Alignment uitvoeren...")
    align_model, align_metadata = whisperx.load_align_model(
        language_code=language, device=device,
    )
    result = whisperx.align(
        result["segments"],
        align_model,
        align_metadata,
        audio,
        device,
        return_char_alignments=False,
    )

    # Geheugen vrijmaken
    del model, align_model
    if device == "mps":
        torch.mps.empty_cache()

    return result, audio


# ---------------------------------------------------------------------------
# Diarization
# ---------------------------------------------------------------------------

def diarize(
    audio,
    result: dict,
    hf_token: str,
    device: str | None = None,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> dict:
    """Voer speaker diarization uit met Pyannote via WhisperX."""
    if device is None:
        device = get_device()

    # Pyannote pipeline draait beter op CPU bij MPS-problemen
    diarize_device = "cpu" if device == "mps" else device

    logger.info("Laden diarization model op %s...", diarize_device)
    diarize_model = whisperx.DiarizationPipeline(
        use_auth_token=hf_token,
        device=diarize_device,
    )

    logger.info("Diarization uitvoeren...")
    diarize_segments = diarize_model(
        audio,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
    )

    result = whisperx.assign_word_speakers(diarize_segments, result)

    del diarize_model
    return result


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def format_timestamp(seconds: float) -> str:
    """Converteer seconden naar HH:MM:SS formaat."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def segments_to_markdown(segments: list[dict], audio_path: str) -> str:
    """Converteer diarized segmenten naar Markdown."""
    lines = []
    filename = Path(audio_path).stem
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append(f"# Transcript: {filename}")
    lines.append(f"\n**Datum:** {now}  ")
    lines.append(f"**Bronbestand:** `{Path(audio_path).name}`\n")
    lines.append("---\n")

    current_speaker = None
    for seg in segments:
        speaker = seg.get("speaker", "ONBEKEND")
        start = format_timestamp(seg.get("start", 0))
        text = seg.get("text", "").strip()

        if not text:
            continue

        if speaker != current_speaker:
            current_speaker = speaker
            lines.append(f"\n### {speaker} [{start}]\n")

        lines.append(f"{text}\n")

    return "\n".join(lines)


def segments_to_json(segments: list[dict], audio_path: str) -> str:
    """Converteer diarized segmenten naar JSON."""
    filename = Path(audio_path).stem
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    data = {
        "filename": filename,
        "source": Path(audio_path).name,
        "date": now,
        "segments": [],
    }

    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        data["segments"].append({
            "speaker": seg.get("speaker", "ONBEKEND"),
            "start": seg.get("start", 0),
            "end": seg.get("end", 0),
            "text": text,
        })

    return json.dumps(data, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Samenvatting via Anthropic
# ---------------------------------------------------------------------------

def generate_summary(transcript_text: str, api_key: str) -> str:
    """Genereer een samenvatting met Claude via de Anthropic API."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    prompt = (
        "Je bent een assistent die vergadernotulen maakt. "
        "Analyseer het volgende transcript en maak een gestructureerde samenvatting "
        "in het Nederlands met de volgende secties:\n\n"
        "1. **Executive Summary** (max 3 zinnen)\n"
        "2. **Besproken onderwerpen** (bullet points)\n"
        "3. **Besluiten** (genummerde lijst)\n"
        "4. **Actiepunten** (tabel met: actie, verantwoordelijke, deadline indien genoemd)\n\n"
        "Indien het transcript deels in het Engels is, vertaal de samenvatting naar het Nederlands.\n\n"
        f"---\n\n{transcript_text}"
    )

    logger.info("Samenvatting genereren via Claude...")
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.argument("audio_path", type=click.Path(exists=True))
@click.option("--model", "model_size", default="large-v3", help="Whisper model (tiny/base/small/medium/large-v3)")
@click.option("--language", default="nl", help="Taal (nl/en)")
@click.option("--hf-token", envvar="HF_TOKEN", default=None, help="HuggingFace token voor Pyannote (of HF_TOKEN env)")
@click.option("--min-speakers", type=int, default=None, help="Minimum aantal sprekers")
@click.option("--max-speakers", type=int, default=None, help="Maximum aantal sprekers")
@click.option("--summarize", is_flag=True, help="Voeg AI-samenvatting toe via Anthropic API")
@click.option("--anthropic-key", envvar="ANTHROPIC_API_KEY", default=None, help="Anthropic API key (of ANTHROPIC_API_KEY env)")
@click.option("--format", "output_format", type=click.Choice(["md", "json"], case_sensitive=False), default="md", help="Output formaat: md (Markdown) of json")
@click.option("--output", "-o", "output_path", default=None, help="Output pad (.md/.json). Default: zelfde naam als input")
@click.option("--keep-audio", is_flag=True, help="Verwijder audiobestand NIET na succesvolle run")
@click.option("--batch-size", type=int, default=8, help="Batch size voor transcriptie")
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
def main(
    audio_path: str,
    model_size: str,
    language: str,
    hf_token: str | None,
    min_speakers: int | None,
    max_speakers: int | None,
    summarize: bool,
    anthropic_key: str | None,
    output_format: str,
    output_path: str | None,
    keep_audio: bool,
    batch_size: int,
    verbose: bool,
):
    """Transcribeer een vergaderopname (m4a) naar Markdown met speaker diarization."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    audio_path = str(Path(audio_path).resolve())

    # Validatie
    if not audio_path.lower().endswith((".m4a", ".wav", ".mp3", ".flac", ".ogg", ".webm")):
        logger.warning("Onverwacht bestandsformaat — wordt toch geprobeerd")

    if hf_token is None:
        logger.warning(
            "Geen HF_TOKEN opgegeven — diarization wordt overgeslagen. "
            "Stel HF_TOKEN in of gebruik --hf-token."
        )

    if summarize and anthropic_key is None:
        click.echo("Fout: --summarize vereist ANTHROPIC_API_KEY (env of --anthropic-key)", err=True)
        sys.exit(1)

    # 1. Transcriberen
    device = get_device()
    result, audio = transcribe_audio(
        audio_path,
        model_size=model_size,
        language=language,
        device=device,
        batch_size=batch_size,
    )

    # 2. Diarization (optioneel)
    if hf_token:
        result = diarize(
            audio,
            result,
            hf_token=hf_token,
            device=device,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )

    # 3. Output genereren
    segments = result.get("segments", [])
    if not segments:
        click.echo("Geen segmenten gevonden in de transcriptie.", err=True)
        sys.exit(1)

    if output_format == "json":
        output_text = segments_to_json(segments, audio_path)
        default_suffix = ".json"

        # 4. Optionele samenvatting (toevoegen als veld in JSON)
        if summarize:
            markdown_for_summary = segments_to_markdown(segments, audio_path)
            summary = generate_summary(markdown_for_summary, anthropic_key)
            data = json.loads(output_text)
            data["summary"] = summary
            output_text = json.dumps(data, ensure_ascii=False, indent=2)
    else:
        output_text = segments_to_markdown(segments, audio_path)
        default_suffix = ".md"

        # 4. Optionele samenvatting
        if summarize:
            summary = generate_summary(output_text, anthropic_key)
            output_text = f"{output_text}\n\n---\n\n## Samenvatting\n\n{summary}\n"

    # 5. Schrijf output
    if output_path is None:
        output_path = str(Path(audio_path).with_suffix(default_suffix))
    Path(output_path).write_text(output_text, encoding="utf-8")
    logger.info("Transcript opgeslagen: %s", output_path)

    # 6. Cleanup
    if not keep_audio:
        Path(audio_path).unlink()
        logger.info("Audiobestand verwijderd: %s", audio_path)

    click.echo(f"\nKlaar! Transcript: {output_path}")
    click.echo(f"Segmenten: {len(segments)}")


if __name__ == "__main__":
    main()
