#!/usr/bin/env python3
"""
Importeer actiepunten uit een e-mail naar Microsoft To Do.

Methode 1 - CSV voor Power Automate (aanbevolen bij geblokkeerde Azure-toegang):
    python email_to_todo.py acties.txt --csv
    python email_to_todo.py --stdin --csv

Methode 2 - Direct via Microsoft Graph API:
    python email_to_todo.py acties.txt
    python email_to_todo.py acties.txt --list "Projectnaam"

Overig:
    python email_to_todo.py acties.txt --dry-run    # Alleen tonen, niets doen

Vereisten:
    pip install click
    pip install msal requests   # alleen nodig voor Graph API methode
"""

import csv
import re
import sys
from pathlib import Path

import click


def parse_tasks(text):
    """
    Extract tasks from email text.

    Herkent:
    - Bullet points: -, *, •
    - Genummerde lijsten: 1., 2), 1:
    - Checkbox-stijl: [ ], [x]
    - Regels na 'actiepunten:', 'to do:', 'taken:', etc.
    """
    lines = text.strip().splitlines()
    tasks = []
    in_action_section = False

    section_pattern = re.compile(
        r"^\s*(actiepunten|acties|actie|taken|to\s*do|action\s*items?|tasks?|todo|opdrachten)\s*[:>\-]?\s*$",
        re.IGNORECASE,
    )

    task_pattern = re.compile(
        r"^\s*"
        r"(?:"
        r"[-*•]\s+"
        r"|\d+[.):\-]\s+"
        r"|\[[ x]?\]\s+"
        r")"
        r"(.+)",
        re.IGNORECASE,
    )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if section_pattern.match(stripped):
            in_action_section = True
            continue

        match = task_pattern.match(line)
        if match:
            task_text = match.group(1).strip()
            # Skip lines that look like section headers rather than tasks
            if task_text and len(task_text) > 2 and not re.match(
                r"^(complete|volledige|snelle)?\s*(actielijst|takenlijst|samenvatting|overzicht)",
                task_text, re.IGNORECASE,
            ):
                tasks.append(task_text)
            continue

        if in_action_section and stripped:
            if not task_pattern.match(line):
                in_action_section = False

    seen = set()
    unique_tasks = []
    for t in tasks:
        normalized = t.lower().strip()
        if normalized not in seen:
            seen.add(normalized)
            unique_tasks.append(t)

    return unique_tasks


def export_csv(tasks, output_path):
    """Export tasks to CSV for Power Automate import."""
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Taak", "Status", "Prioriteit"])
        for task in tasks:
            writer.writerow([task, "Niet gestart", "Normaal"])
    return output_path


# --- Graph API methode (optioneel) ---

GRAPH_API = "https://graph.microsoft.com/v1.0"
CLIENT_ID = "04b07795-a710-4532-b849-46c9bccfb18c"
SCOPES = ["Tasks.ReadWrite"]
TOKEN_CACHE_FILE = Path.home() / ".ms_todo_token_cache.json"


def authenticate():
    """Authenticate via device code flow and return access token."""
    import msal

    cache = msal.SerializableTokenCache()
    if TOKEN_CACHE_FILE.exists():
        cache.deserialize(TOKEN_CACHE_FILE.read_text())

    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority="https://login.microsoftonline.com/common",
        token_cache=cache,
    )

    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            if cache.has_state_changed:
                TOKEN_CACHE_FILE.write_text(cache.serialize())
            return result["access_token"]

    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise click.ClickException(f"Authenticatie mislukt: {flow.get('error_description', 'onbekende fout')}")

    click.echo(f"\n{flow['message']}\n")
    result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        raise click.ClickException(f"Authenticatie mislukt: {result.get('error_description', 'onbekende fout')}")

    if cache.has_state_changed:
        TOKEN_CACHE_FILE.write_text(cache.serialize())
    return result["access_token"]


class TodoClient:
    """Microsoft To Do API client."""

    def __init__(self, token):
        import requests
        self.requests = requests
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })

    def _get(self, url):
        resp = self.session.get(f"{GRAPH_API}{url}")
        resp.raise_for_status()
        return resp.json()

    def _post(self, url, data):
        resp = self.session.post(f"{GRAPH_API}{url}", json=data)
        resp.raise_for_status()
        return resp.json()

    def get_lists(self):
        return self._get("/me/todo/lists")["value"]

    def find_or_create_list(self, name):
        lists = self.get_lists()
        for lst in lists:
            if lst["displayName"].lower() == name.lower():
                return lst["id"]
        result = self._post("/me/todo/lists", {"displayName": name})
        return result["id"]

    def get_default_list(self):
        lists = self.get_lists()
        for lst in lists:
            if lst.get("wellknownListName") == "defaultList":
                return lst["id"]
        return lists[0]["id"] if lists else None

    def create_task(self, list_id, title):
        return self._post(f"/me/todo/lists/{list_id}/tasks", {"title": title})

    def create_tasks_batch(self, list_id, task_titles):
        created = []
        errors = []
        for i, title in enumerate(task_titles, 1):
            try:
                task = self.create_task(list_id, title)
                created.append(task)
                click.echo(f"  [{i}/{len(task_titles)}] {title}")
            except self.requests.HTTPError as e:
                errors.append((title, str(e)))
                click.echo(f"  [{i}/{len(task_titles)}] FOUT: {title} - {e}")
        return created, errors


@click.command()
@click.argument("file", required=False, type=click.Path(exists=True))
@click.option("--stdin", "use_stdin", is_flag=True, help="Lees e-mailtekst van stdin")
@click.option("--csv", "use_csv", is_flag=True, help="Exporteer naar CSV (voor Power Automate)")
@click.option("--output", "-o", default=None, help="Output CSV-bestandsnaam")
@click.option("--list", "list_name", default=None, help="Naam van de takenlijst (Graph API)")
@click.option("--dry-run", is_flag=True, help="Toon gevonden taken zonder ze aan te maken")
def main(file, use_stdin, use_csv, output, list_name, dry_run):
    """Importeer actiepunten uit een e-mail naar Microsoft To Do."""

    # Read input
    if use_stdin:
        click.echo("Plak de e-mailtekst en sluit af met Ctrl+D:\n")
        text = sys.stdin.read()
    elif file:
        text = Path(file).read_text(encoding="utf-8")
    else:
        raise click.UsageError("Geef een bestand op of gebruik --stdin")

    if not text.strip():
        raise click.ClickException("Geen tekst gevonden.")

    # Parse tasks
    tasks = parse_tasks(text)

    if not tasks:
        click.echo("Geen actiepunten gevonden in de tekst.")
        click.echo("\nTip: Zorg dat de taken als bullet points (-, *) of genummerd (1., 2.) zijn opgemaakt,")
        click.echo("of dat ze onder een kopje als 'Actiepunten:' of 'To do:' staan.")
        return

    click.echo(f"\n{len(tasks)} actiepunten gevonden:\n")
    for i, task in enumerate(tasks, 1):
        click.echo(f"  {i}. {task}")

    if dry_run:
        click.echo("\n(Dry-run: geen taken aangemaakt)")
        return

    # CSV export voor Power Automate
    if use_csv:
        csv_path = output or (Path(file).stem + "_taken.csv" if file else "taken.csv")
        export_csv(tasks, csv_path)
        click.echo(f"\nCSV opgeslagen: {csv_path}")
        click.echo("\nVolgende stappen in Power Automate:")
        click.echo("  1. Ga naar make.powerautomate.com")
        click.echo("  2. Maak een 'Instant cloud flow' (handmatig triggeren)")
        click.echo("  3. Voeg de Excel-connector toe om rijen uit het CSV te lezen")
        click.echo("  4. Voeg 'Apply to each' toe met de actie 'Microsoft To Do - Taak maken'")
        click.echo("  5. Koppel het veld 'Taak' aan de taaknaam")
        click.echo("  6. Draai de flow")
        return

    # Graph API methode
    click.echo("\nVerbinden met Microsoft To Do...")
    token = authenticate()
    client = TodoClient(token)

    if list_name:
        list_id = client.find_or_create_list(list_name)
        click.echo(f"Takenlijst: {list_name}")
    else:
        list_id = client.get_default_list()
        click.echo("Takenlijst: Taken (standaard)")

    click.echo(f"\n{len(tasks)} taken aanmaken...\n")
    created, errors = client.create_tasks_batch(list_id, tasks)

    click.echo(f"\nKlaar! {len(created)} taken aangemaakt.", nl=False)
    if errors:
        click.echo(f" ({len(errors)} fouten)")
    else:
        click.echo()


if __name__ == "__main__":
    main()
