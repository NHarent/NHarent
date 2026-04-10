"""
Configuratiebeheer voor NHarent automatiseringen.

Laadt instellingen uit config.yaml en environment variables.
API keys worden altijd uit environment variables gelezen (nooit in config.yaml).
"""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".nharent"
CONFIG_FILE = CONFIG_DIR / "config.json"
TOKEN_CACHE = CONFIG_DIR / "token_cache.json"


@dataclass
class GraphConfig:
    """Microsoft Graph API configuratie."""
    client_id: str = ""
    tenant_id: str = "common"
    scopes: list[str] = field(default_factory=lambda: [
        "Mail.Read",
        "Calendars.Read",
        "Tasks.ReadWrite",
        "User.Read",
    ])


@dataclass
class AutomationConfig:
    """Centrale configuratie voor alle automatiseringen."""
    # Microsoft Graph
    graph: GraphConfig = field(default_factory=GraphConfig)

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Automation instellingen
    mail_check_count: int = 20
    calendar_days_ahead: int = 7
    task_list_name: str = "NHarent Acties"
    language: str = "nl"
    verbose: bool = False

    # Paden
    transcript_dir: str = ""


def load_config() -> AutomationConfig:
    """Laad configuratie uit config.json en environment variables."""
    config = AutomationConfig()

    # Laad uit bestand indien aanwezig
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            _apply_dict(config, data)
            logger.info("Configuratie geladen uit %s", CONFIG_FILE)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Fout bij laden config: %s", e)

    # Environment variables overschrijven altijd het bestand
    config.anthropic_api_key = os.environ.get(
        "ANTHROPIC_API_KEY", config.anthropic_api_key
    )
    config.graph.client_id = os.environ.get(
        "MS_CLIENT_ID", config.graph.client_id
    )
    config.graph.tenant_id = os.environ.get(
        "MS_TENANT_ID", config.graph.tenant_id
    )

    return config


def save_config(config: AutomationConfig) -> None:
    """Sla configuratie op (zonder API keys)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    data = {
        "graph": {
            "client_id": config.graph.client_id,
            "tenant_id": config.graph.tenant_id,
            "scopes": config.graph.scopes,
        },
        "anthropic_model": config.anthropic_model,
        "mail_check_count": config.mail_check_count,
        "calendar_days_ahead": config.calendar_days_ahead,
        "task_list_name": config.task_list_name,
        "language": config.language,
        "transcript_dir": config.transcript_dir,
    }

    CONFIG_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Configuratie opgeslagen in %s", CONFIG_FILE)


def init_config_interactive() -> AutomationConfig:
    """Interactieve eerste configuratie."""
    print("\n🔧 NHarent Automatisering — Eerste configuratie\n")
    print("Stap 1: Microsoft Graph API (voor Outlook, Agenda, To Do)")
    print("  Registreer een app op https://portal.azure.com/#view/"
          "Microsoft_AAD_RegisteredApps/ApplicationsListBlade")
    print("  Kies 'Public client/native' als platform en voeg")
    print("  http://localhost als redirect URI toe.\n")

    config = AutomationConfig()

    config.graph.client_id = input("  MS_CLIENT_ID: ").strip()
    config.graph.tenant_id = input(
        "  MS_TENANT_ID [common]: "
    ).strip() or "common"

    print("\nStap 2: Anthropic API key")
    print("  Haal een key op via https://console.anthropic.com/\n")
    anthropic_key = input("  ANTHROPIC_API_KEY: ").strip()

    if anthropic_key:
        print("\n  ⚠️  Sla je ANTHROPIC_API_KEY op als environment variable:")
        print(f"  export ANTHROPIC_API_KEY='{anthropic_key}'")

    config.task_list_name = input(
        "\nNaam voor je To Do-lijst [NHarent Acties]: "
    ).strip() or "NHarent Acties"

    config.transcript_dir = input(
        "Map met vergadertranscripties [leeg = huidige map]: "
    ).strip()

    save_config(config)
    print(f"\n✅ Configuratie opgeslagen in {CONFIG_FILE}")
    return config


def _apply_dict(config: AutomationConfig, data: dict) -> None:
    """Pas dictionary-waarden toe op config object."""
    if "graph" in data:
        g = data["graph"]
        config.graph.client_id = g.get("client_id", config.graph.client_id)
        config.graph.tenant_id = g.get("tenant_id", config.graph.tenant_id)
        config.graph.scopes = g.get("scopes", config.graph.scopes)

    for key in (
        "anthropic_model", "mail_check_count", "calendar_days_ahead",
        "task_list_name", "language", "transcript_dir", "verbose",
    ):
        if key in data:
            setattr(config, key, data[key])
