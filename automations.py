#!/usr/bin/env python3
"""
NHarent Automation Runner — Centrale orchestratie.

Verbindt Microsoft Graph (Outlook, Agenda, To Do) met AI-gestuurde
taakextractie om dagelijks slimme actiepunten te genereren en te beheren.

Gebruik:
    python automations.py run          # Volledige dagelijkse run
    python automations.py mail         # Alleen e-mail acties extraheren
    python automations.py calendar     # Alleen agenda acties extraheren
    python automations.py transcript   # Acties uit transcripties extraheren
    python automations.py briefing     # Dagelijkse briefing genereren
    python automations.py setup        # Eerste configuratie
    python automations.py status       # Toon status en open taken
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import click

from config import AutomationConfig, load_config, init_config_interactive
from graph_client import GraphClient
from ai_tasks import AITaskExtractor, ExtractedTask

logger = logging.getLogger(__name__)


class AutomationRunner:
    """Orkestratielaag die alles aan elkaar knoopt."""

    def __init__(self, config: AutomationConfig):
        self.config = config
        self.graph: GraphClient | None = None
        self.ai: AITaskExtractor | None = None
        self._task_list_id: str | None = None

    def init_graph(self) -> bool:
        """Initialiseer en authenticeer Graph API client."""
        if not self.config.graph.client_id:
            logger.error("MS_CLIENT_ID niet geconfigureerd. Draai: "
                         "python automations.py setup")
            return False

        self.graph = GraphClient(self.config.graph)
        if not self.graph.authenticate():
            logger.error("Microsoft authenticatie mislukt")
            return False
        return True

    def init_ai(self) -> bool:
        """Initialiseer AI taakextractor."""
        if not self.config.anthropic_api_key:
            logger.error("ANTHROPIC_API_KEY niet geconfigureerd")
            return False

        self.ai = AITaskExtractor(
            api_key=self.config.anthropic_api_key,
            model=self.config.anthropic_model,
        )
        return True

    # ------------------------------------------------------------------
    # Automatiseringsflows
    # ------------------------------------------------------------------

    def run_full(self) -> None:
        """Volledige dagelijkse automatisering."""
        print("\n📋 NHarent Dagelijkse Automatisering\n")
        print(f"   Datum: {datetime.now().strftime('%A %d %B %Y')}")
        print("=" * 50)

        all_tasks: list[ExtractedTask] = []

        # 1. E-mail actiepunten
        print("\n📧 E-mails analyseren...")
        mail_tasks = self.extract_mail_tasks()
        all_tasks.extend(mail_tasks)
        print(f"   → {len(mail_tasks)} actiepunten gevonden")

        # 2. Agenda voorbereiding
        print("\n📅 Agenda analyseren...")
        cal_tasks = self.extract_calendar_tasks()
        all_tasks.extend(cal_tasks)
        print(f"   → {len(cal_tasks)} voorbereidingen gevonden")

        # 3. Transcripties verwerken
        print("\n🎙️  Transcripties analyseren...")
        transcript_tasks = self.extract_transcript_tasks()
        all_tasks.extend(transcript_tasks)
        print(f"   → {len(transcript_tasks)} actiepunten gevonden")

        # 4. AI prioritering
        if all_tasks and self.ai:
            print("\n🤖 Taken prioriteren met AI...")
            all_tasks = self.ai.prioritize_tasks(all_tasks)
            print(f"   → {len(all_tasks)} unieke taken na deduplicatie")

        # 5. Naar Microsoft To Do pushen
        if all_tasks:
            print("\n✅ Taken naar Microsoft To Do pushen...")
            created = self.push_tasks_to_todo(all_tasks)
            print(f"   → {created} taken aangemaakt")

        # 6. Dagelijkse briefing
        if self.ai:
            print("\n📝 Dagelijkse briefing genereren...\n")
            events_today = self._get_today_events()
            briefing = self.ai.generate_daily_briefing(
                all_tasks, events_today
            )
            print("─" * 50)
            print(briefing)
            print("─" * 50)

        print(f"\n✅ Klaar! {len(all_tasks)} taken verwerkt.\n")

    def extract_mail_tasks(self) -> list[ExtractedTask]:
        """Extraheer actiepunten uit recente e-mails."""
        if not self.graph or not self.ai:
            return []

        mails = self.graph.get_recent_mail(count=self.config.mail_check_count)
        return self.ai.extract_from_emails(mails)

    def extract_calendar_tasks(self) -> list[ExtractedTask]:
        """Extraheer voorbereidingstaken uit agenda."""
        if not self.graph or not self.ai:
            return []

        events = self.graph.get_upcoming_events(
            days_ahead=self.config.calendar_days_ahead
        )
        return self.ai.extract_from_calendar(events)

    def extract_transcript_tasks(self) -> list[ExtractedTask]:
        """Extraheer actiepunten uit recente vergadertranscripties."""
        if not self.ai:
            return []

        search_dir = Path(self.config.transcript_dir or ".")
        if not search_dir.exists():
            return []

        # Zoek .md bestanden van de afgelopen 7 dagen
        cutoff = datetime.now().timestamp() - (7 * 86400)
        transcripts = [
            p for p in search_dir.glob("*.md")
            if p.stat().st_mtime > cutoff
            and p.name != "README.md"
        ]

        all_tasks: list[ExtractedTask] = []
        for path in transcripts:
            tasks = self.ai.extract_from_transcript(str(path))
            all_tasks.extend(tasks)

        return all_tasks

    def push_tasks_to_todo(
        self, tasks: list[ExtractedTask]
    ) -> int:
        """Push taken naar Microsoft To Do."""
        if not self.graph:
            return 0

        list_id = self._get_task_list_id()
        if not list_id:
            return 0

        # Haal bestaande taken op om duplicaten te voorkomen
        existing = self.graph.get_tasks(list_id)
        existing_titles = {t["title"].lower() for t in existing}

        created = 0
        for task in tasks:
            if task.title.lower() in existing_titles:
                logger.info("Overgeslagen (bestaat al): %s", task.title)
                continue

            importance_map = {
                "high": "high",
                "normal": "normal",
                "low": "low",
            }

            body_parts = []
            if task.description:
                body_parts.append(task.description)
            if task.source:
                body_parts.append(f"\nBron: {task.source}")
            if task.owner:
                body_parts.append(f"Eigenaar: {task.owner}")

            self.graph.create_task(
                list_id=list_id,
                title=task.title,
                body="\n".join(body_parts),
                due_date=task.due_date,
                importance=importance_map.get(task.priority, "normal"),
            )
            created += 1

        return created

    def show_status(self) -> None:
        """Toon huidige status en open taken."""
        if not self.graph:
            return

        list_id = self._get_task_list_id()
        if not list_id:
            print("Geen takenlijst gevonden.")
            return

        tasks = self.graph.get_tasks(list_id)

        print(f"\n📋 Open taken in '{self.config.task_list_name}':\n")

        if not tasks:
            print("   Geen open taken — goed bezig! 🎉\n")
            return

        for i, task in enumerate(tasks, 1):
            icon = {"high": "🔴", "normal": "🟡", "low": "🟢"}.get(
                task.get("importance", "normal"), "⚪"
            )
            due = ""
            if task.get("dueDateTime"):
                due_date = task["dueDateTime"]["dateTime"][:10]
                due = f" (deadline: {due_date})"

            print(f"   {icon} {i}. {task['title']}{due}")

        print(f"\n   Totaal: {len(tasks)} open taken\n")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_task_list_id(self) -> str | None:
        if self._task_list_id:
            return self._task_list_id

        if not self.graph:
            return None

        self._task_list_id = self.graph.get_or_create_task_list(
            self.config.task_list_name
        )
        return self._task_list_id

    def _get_today_events(self) -> list[dict]:
        if not self.graph:
            return []
        return self.graph.get_upcoming_events(days_ahead=1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
@click.pass_context
def cli(ctx, verbose):
    """NHarent — Slimme automatiseringen voor dagelijks taakbeheer."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@cli.command()
def setup():
    """Eerste configuratie doorlopen."""
    init_config_interactive()


@cli.command()
@click.pass_context
def run(ctx):
    """Volledige dagelijkse automatisering draaien."""
    runner = _create_runner()
    if not runner:
        sys.exit(1)
    runner.run_full()


@cli.command()
@click.pass_context
def mail(ctx):
    """Actiepunten extraheren uit e-mails."""
    runner = _create_runner()
    if not runner:
        sys.exit(1)

    tasks = runner.extract_mail_tasks()
    _print_tasks(tasks, "E-mail actiepunten")


@cli.command()
@click.pass_context
def calendar(ctx):
    """Voorbereidingen extraheren uit agenda."""
    runner = _create_runner()
    if not runner:
        sys.exit(1)

    tasks = runner.extract_calendar_tasks()
    _print_tasks(tasks, "Agenda voorbereidingen")


@cli.command()
@click.argument("path", required=False)
@click.pass_context
def transcript(ctx, path):
    """Actiepunten extraheren uit vergadertranscript(en)."""
    runner = _create_runner(graph_required=False)
    if not runner:
        sys.exit(1)

    if path:
        tasks = runner.ai.extract_from_transcript(path)
    else:
        tasks = runner.extract_transcript_tasks()

    _print_tasks(tasks, "Vergadering actiepunten")


@cli.command()
@click.pass_context
def briefing(ctx):
    """Dagelijkse briefing genereren."""
    runner = _create_runner()
    if not runner:
        sys.exit(1)

    all_tasks = (
        runner.extract_mail_tasks()
        + runner.extract_calendar_tasks()
    )

    if runner.ai:
        all_tasks = runner.ai.prioritize_tasks(all_tasks)
        events = runner._get_today_events()
        print("\n" + runner.ai.generate_daily_briefing(all_tasks, events))


@cli.command()
@click.pass_context
def status(ctx):
    """Toon status en open taken."""
    runner = _create_runner(ai_required=False)
    if not runner:
        sys.exit(1)
    runner.show_status()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_runner(
    graph_required: bool = True,
    ai_required: bool = True,
) -> AutomationRunner | None:
    """Maak runner aan met de juiste componenten."""
    config = load_config()
    runner = AutomationRunner(config)

    if graph_required:
        if not runner.init_graph():
            return None

    if ai_required:
        if not runner.init_ai():
            return None

    return runner


def _print_tasks(tasks: list[ExtractedTask], header: str) -> None:
    """Print taken naar console."""
    print(f"\n📋 {header}:\n")

    if not tasks:
        print("   Geen actiepunten gevonden.\n")
        return

    for i, task in enumerate(tasks, 1):
        icon = {"high": "🔴", "normal": "🟡", "low": "🟢"}.get(
            task.priority, "⚪"
        )
        due = f" (deadline: {task.due_date})" if task.due_date else ""
        print(f"   {icon} {i}. {task.title}{due}")
        if task.description:
            print(f"      {task.description[:80]}")
        if task.source:
            print(f"      📎 {task.source}")
        print()

    print(f"   Totaal: {len(tasks)} actiepunten\n")


if __name__ == "__main__":
    cli()
