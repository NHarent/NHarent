"""
AI-gestuurde taakextractie en prioritering met Claude.

Analyseert e-mails, agenda-items en vergadertranscripties om
actiepunten te extraheren, te prioriteren en om te zetten in taken.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTask:
    """Een geextraheerd actiepunt."""
    title: str
    description: str = ""
    due_date: str | None = None  # YYYY-MM-DD
    priority: str = "normal"     # low / normal / high
    source: str = ""             # Waar het actiepunt vandaan komt
    owner: str = ""              # Wie verantwoordelijk is


class AITaskExtractor:
    """Extraheert en prioriteert taken uit diverse bronnen via Claude."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def extract_from_emails(
        self, emails: list[dict], user_name: str = ""
    ) -> list[ExtractedTask]:
        """Extraheer actiepunten uit een lijst e-mails."""
        if not emails:
            return []

        email_text = self._format_emails(emails)
        prompt = (
            "Je bent een slimme persoonlijke assistent. Analyseer de volgende "
            "e-mails en extraheer ALLEEN concrete actiepunten die actie "
            "vereisen van de gebruiker"
            + (f" ({user_name})" if user_name else "")
            + ".\n\n"
            "Negeer nieuwsbrieven, notificaties en informationele e-mails "
            "zonder actiepunt.\n\n"
            "Retourneer een JSON array met objecten:\n"
            '[\n  {\n    "title": "korte actietitel",\n'
            '    "description": "context en details",\n'
            '    "due_date": "YYYY-MM-DD of null",\n'
            '    "priority": "low/normal/high",\n'
            '    "source": "Van: afzender — Onderwerp: onderwerp"\n'
            "  }\n]\n\n"
            "Retourneer een lege array [] als er geen actiepunten zijn.\n"
            "Antwoord ALLEEN met valid JSON, geen uitleg.\n\n"
            f"---\n\n{email_text}"
        )

        return self._extract(prompt, source_type="email")

    def extract_from_calendar(
        self, events: list[dict]
    ) -> list[ExtractedTask]:
        """Extraheer voorbereidingstaken uit agenda-events."""
        if not events:
            return []

        events_text = self._format_events(events)
        prompt = (
            "Je bent een slimme persoonlijke assistent. Analyseer de volgende "
            "agenda-items en identificeer acties die de gebruiker moet "
            "voorbereiden of opvolgen.\n\n"
            "Denk aan:\n"
            "- Vergaderingen die voorbereiding nodig hebben\n"
            "- Deadlines die naderen\n"
            "- Follow-ups na afspraken\n\n"
            "Retourneer een JSON array met objecten:\n"
            '[\n  {\n    "title": "korte actietitel",\n'
            '    "description": "wat moet er voorbereid/gedaan worden",\n'
            '    "due_date": "YYYY-MM-DD (dag voor het event)",\n'
            '    "priority": "low/normal/high",\n'
            '    "source": "Agenda: eventnaam op datum"\n'
            "  }\n]\n\n"
            "Retourneer een lege array [] als er geen acties nodig zijn.\n"
            "Antwoord ALLEEN met valid JSON, geen uitleg.\n\n"
            f"---\n\n{events_text}"
        )

        return self._extract(prompt, source_type="calendar")

    def extract_from_transcript(
        self, transcript_path: str
    ) -> list[ExtractedTask]:
        """Extraheer actiepunten uit een vergadertranscript."""
        path = Path(transcript_path)
        if not path.exists():
            logger.warning("Transcript niet gevonden: %s", transcript_path)
            return []

        text = path.read_text(encoding="utf-8")
        # Beperk tot ~12000 tokens (~48000 chars)
        if len(text) > 48000:
            text = text[:48000] + "\n\n[... ingekort ...]"

        prompt = (
            "Je bent een slimme persoonlijke assistent. Analyseer het volgende "
            "vergadertranscript en extraheer ALLE concrete actiepunten.\n\n"
            "Let specifiek op:\n"
            "- Taken die aan personen zijn toegewezen\n"
            "- Deadlines die genoemd zijn\n"
            "- Beslissingen die opvolging vereisen\n"
            "- Afspraken over volgende stappen\n\n"
            "Retourneer een JSON array met objecten:\n"
            '[\n  {\n    "title": "korte actietitel",\n'
            '    "description": "context uit de vergadering",\n'
            '    "due_date": "YYYY-MM-DD of null",\n'
            '    "priority": "low/normal/high",\n'
            '    "owner": "naam van de verantwoordelijke indien genoemd",\n'
            '    "source": "Vergadering: titel"\n'
            "  }\n]\n\n"
            "Retourneer een lege array [] als er geen actiepunten zijn.\n"
            "Antwoord ALLEEN met valid JSON, geen uitleg.\n\n"
            f"---\n\n{text}"
        )

        return self._extract(prompt, source_type="transcript")

    def prioritize_tasks(
        self, tasks: list[ExtractedTask]
    ) -> list[ExtractedTask]:
        """Herprioriteer en dedupliceer een lijst taken met AI."""
        if len(tasks) <= 1:
            return tasks

        tasks_json = json.dumps(
            [_task_to_dict(t) for t in tasks],
            ensure_ascii=False, indent=2,
        )

        prompt = (
            "Je bent een slimme persoonlijke assistent. Hieronder staat een "
            "lijst actiepunten uit verschillende bronnen (e-mail, agenda, "
            "vergaderingen).\n\n"
            "Doe het volgende:\n"
            "1. Verwijder duplicaten (houd de meest complete versie)\n"
            "2. Prioriteer op urgentie en impact (high/normal/low)\n"
            "3. Sorteer van hoogste naar laagste prioriteit\n"
            "4. Voeg ontbrekende deadlines toe als je ze kunt afleiden\n\n"
            "Retourneer de opgeschoonde JSON array in hetzelfde formaat.\n"
            "Antwoord ALLEEN met valid JSON, geen uitleg.\n\n"
            f"---\n\n{tasks_json}"
        )

        return self._extract(prompt, source_type="prioritized")

    def generate_daily_briefing(
        self,
        tasks: list[ExtractedTask],
        events: list[dict] | None = None,
    ) -> str:
        """Genereer een dagelijkse briefing in het Nederlands."""
        tasks_text = "\n".join(
            f"- [{t.priority.upper()}] {t.title}"
            + (f" (deadline: {t.due_date})" if t.due_date else "")
            for t in tasks
        )

        events_text = ""
        if events:
            events_text = "\n\nAgenda vandaag:\n" + "\n".join(
                f"- {e.get('start', {}).get('dateTime', '?')[:16]} "
                f"— {e.get('subject', 'Geen titel')}"
                for e in events
            )

        prompt = (
            "Je bent een vriendelijke persoonlijke assistent. Schrijf een "
            "beknopte dagbriefing in het Nederlands (max 200 woorden).\n\n"
            "Benoem:\n"
            "1. De belangrijkste 3 taken van vandaag\n"
            "2. Eventuele afspraken\n"
            "3. Deadlines die naderen\n\n"
            "Gebruik een informele, directe toon.\n\n"
            f"Taken:\n{tasks_text}{events_text}"
        )

        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract(
        self, prompt: str, source_type: str = ""
    ) -> list[ExtractedTask]:
        """Stuur prompt naar Claude en parse JSON response."""
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()

            # Strip markdown code fences indien aanwezig
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            items = json.loads(raw)

            tasks = []
            for item in items:
                tasks.append(ExtractedTask(
                    title=item.get("title", "Onbekende taak"),
                    description=item.get("description", ""),
                    due_date=item.get("due_date"),
                    priority=item.get("priority", "normal"),
                    source=item.get("source", source_type),
                    owner=item.get("owner", ""),
                ))

            logger.info("%d taken geextraheerd (%s)", len(tasks), source_type)
            return tasks

        except json.JSONDecodeError as e:
            logger.error("Kon JSON niet parsen uit AI response: %s", e)
            return []
        except Exception as e:
            logger.error("Fout bij taakextractie: %s", e)
            return []

    @staticmethod
    def _format_emails(emails: list[dict]) -> str:
        parts = []
        for mail in emails:
            sender = mail.get("from", {}).get(
                "emailAddress", {}
            ).get("name", "Onbekend")
            parts.append(
                f"Van: {sender}\n"
                f"Onderwerp: {mail.get('subject', '(geen)')}\n"
                f"Datum: {mail.get('receivedDateTime', '?')}\n"
                f"Belang: {mail.get('importance', 'normal')}\n"
                f"Preview: {mail.get('bodyPreview', '')}\n"
                f"---"
            )
        return "\n".join(parts)

    @staticmethod
    def _format_events(events: list[dict]) -> str:
        parts = []
        for ev in events:
            start = ev.get("start", {}).get("dateTime", "?")[:16]
            end = ev.get("end", {}).get("dateTime", "?")[:16]
            organizer = ev.get("organizer", {}).get(
                "emailAddress", {}
            ).get("name", "?")
            parts.append(
                f"Event: {ev.get('subject', 'Geen titel')}\n"
                f"Start: {start}  Eind: {end}\n"
                f"Organisator: {organizer}\n"
                f"Preview: {ev.get('bodyPreview', '')}\n"
                f"Online: {ev.get('isOnlineMeeting', False)}\n"
                f"---"
            )
        return "\n".join(parts)


def _task_to_dict(task: ExtractedTask) -> dict:
    return {
        "title": task.title,
        "description": task.description,
        "due_date": task.due_date,
        "priority": task.priority,
        "source": task.source,
        "owner": task.owner,
    }
