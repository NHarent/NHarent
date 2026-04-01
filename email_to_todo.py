#!/usr/bin/env python3
"""
Importeer actiepunten uit een e-mail naar Microsoft To Do.

Gebruik:
    # Vanuit een tekstbestand
    python email_to_todo.py acties.txt

    # Plak e-mailtekst via stdin
    python email_to_todo.py --stdin

    # Met specifieke takenlijst
    python email_to_todo.py acties.txt --list "Projectnaam"

    # Dry-run: laat zien welke taken gevonden worden zonder ze aan te maken
    python email_to_todo.py acties.txt --dry-run

Vereisten:
    pip install msal requests click

Authenticatie:
    Bij eerste gebruik wordt een device code flow gestart.
    Je logt in via https://microsoft.com/devicelogin met je Microsoft-account.
    Het token wordt lokaal gecached in .ms_todo_token_cache.json
"""

import json
import re
import sys
from pathlib import Path

import click
import msal
import requests

# Microsoft Graph API settings
GRAPH_API = "https://graph.microsoft.com/v1.0"
CLIENT_ID = "04b07795-a710-4532-b849-46c9bccfb18c"  # Azure CLI public client ID
SCOPES = ["Tasks.ReadWrite"]
TOKEN_CACHE_FILE = Path.home() / ".ms_todo_token_cache.json"


def get_token_cache():
    """Load or create MSAL token cache."""
    cache = msal.SerializableTokenCache()
    if TOKEN_CACHE_FILE.exists():
        cache.deserialize(TOKEN_CACHE_FILE.read_text())
    return cache


def save_token_cache(cache):
    """Persist token cache to disk."""
    if cache.has_state_changed:
        TOKEN_CACHE_FILE.write_text(cache.serialize())


def authenticate():
    """Authenticate via device code flow and return access token."""
    cache = get_token_cache()
    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority="https://login.microsoftonline.com/common",
        token_cache=cache,
    )

    # Try silent auth first (cached token)
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            save_token_cache(cache)
            return result["access_token"]

    # Device code flow
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise click.ClickException(f"Authenticatie mislukt: {flow.get('error_description', 'onbekende fout')}")

    click.echo(f"\n🔐 {flow['message']}\n")
    result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        raise click.ClickException(f"Authenticatie mislukt: {result.get('error_description', 'onbekende fout')}")

    save_token_cache(cache)
    return result["access_token"]


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

    # Patterns for section headers that indicate action items follow
    section_pattern = re.compile(
        r"^\s*(actiepunten|acties|actie|taken|to\s*do|action\s*items?|tasks?|todo|opdrachten)\s*[:>\-]?\s*$",
        re.IGNORECASE,
    )

    # Pattern for task lines
    task_pattern = re.compile(
        r"^\s*"
        r"(?:"
        r"[-*•]\s+"              # bullet: -, *, •
        r"|\d+[.):\-]\s+"       # numbered: 1. 2) 3: 4-
        r"|\[[ x]?\]\s+"        # checkbox: [ ], [x]
        r")"
        r"(.+)",
        re.IGNORECASE,
    )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check if this is an action section header
        if section_pattern.match(stripped):
            in_action_section = True
            continue

        # Check if line matches a task pattern
        match = task_pattern.match(line)
        if match:
            task_text = match.group(1).strip()
            if task_text and len(task_text) > 2:
                tasks.append(task_text)
            continue

        # If we're in an action section, only continue if line looks like a task
        if in_action_section and stripped:
            # A non-bullet line after a blank line or without task formatting ends the section
            if not task_pattern.match(line):
                in_action_section = False

    # Deduplicate while preserving order
    seen = set()
    unique_tasks = []
    for t in tasks:
        normalized = t.lower().strip()
        if normalized not in seen:
            seen.add(normalized)
            unique_tasks.append(t)

    return unique_tasks


class TodoClient:
    """Microsoft To Do API client."""

    def __init__(self, token):
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
        """Get all task lists."""
        return self._get("/me/todo/lists")["value"]

    def find_or_create_list(self, name):
        """Find a task list by name, or create it."""
        lists = self.get_lists()
        for lst in lists:
            if lst["displayName"].lower() == name.lower():
                return lst["id"]

        result = self._post("/me/todo/lists", {"displayName": name})
        return result["id"]

    def get_default_list(self):
        """Get the default 'Tasks' list."""
        lists = self.get_lists()
        # The default list usually has wellknownListName == "defaultList"
        for lst in lists:
            if lst.get("wellknownListName") == "defaultList":
                return lst["id"]
        # Fallback to first list
        return lists[0]["id"] if lists else None

    def create_task(self, list_id, title, body=None):
        """Create a single task in a list."""
        task_data = {"title": title}
        if body:
            task_data["body"] = {"content": body, "contentType": "text"}
        return self._post(f"/me/todo/lists/{list_id}/tasks", task_data)

    def create_tasks_batch(self, list_id, task_titles):
        """Create multiple tasks. Returns list of created tasks."""
        created = []
        errors = []
        for i, title in enumerate(task_titles, 1):
            try:
                task = self.create_task(list_id, title)
                created.append(task)
                click.echo(f"  [{i}/{len(task_titles)}] {title}")
            except requests.HTTPError as e:
                errors.append((title, str(e)))
                click.echo(f"  [{i}/{len(task_titles)}] FOUT: {title} - {e}")
        return created, errors


@click.command()
@click.argument("file", required=False, type=click.Path(exists=True))
@click.option("--stdin", "use_stdin", is_flag=True, help="Lees e-mailtekst van stdin")
@click.option("--list", "list_name", default=None, help="Naam van de takenlijst (wordt aangemaakt als die niet bestaat)")
@click.option("--dry-run", is_flag=True, help="Toon gevonden taken zonder ze aan te maken")
def main(file, use_stdin, list_name, dry_run):
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

    # Authenticate
    click.echo("\nVerbinden met Microsoft To Do...")
    token = authenticate()
    client = TodoClient(token)

    # Get or create list
    if list_name:
        list_id = client.find_or_create_list(list_name)
        click.echo(f"Takenlijst: {list_name}")
    else:
        list_id = client.get_default_list()
        click.echo("Takenlijst: Taken (standaard)")

    # Create tasks
    click.echo(f"\n{len(tasks)} taken aanmaken...\n")
    created, errors = client.create_tasks_batch(list_id, tasks)

    # Summary
    click.echo(f"\nKlaar! {len(created)} taken aangemaakt.", nl=False)
    if errors:
        click.echo(f" ({len(errors)} fouten)")
    else:
        click.echo()


if __name__ == "__main__":
    main()
