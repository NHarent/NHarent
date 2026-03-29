"""Configuration for the woningmonitor."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SearchFilter:
    """Search criteria for house listings."""
    plaats: str = "Amsterdam"
    straal_km: int = 10
    min_prijs: int = 0
    max_prijs: int = 1_000_000
    min_oppervlakte: int = 0  # m²
    min_kamers: int = 0
    woningtype: list[str] = field(default_factory=lambda: [
        "appartement", "tussenwoning", "hoekwoning", "vrijstaand",
        "twee-onder-een-kap", "penthouse", "grachtenpand"
    ])


@dataclass
class NotificationConfig:
    """Notification settings."""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_from: str = ""
    email_to: str = ""
    email_password: str = ""
    ntfy_topic: str = ""  # ntfy.sh push notifications
    ntfy_server: str = "https://ntfy.sh"


@dataclass
class Config:
    """Main configuration."""
    search: SearchFilter = field(default_factory=SearchFilter)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    check_interval_minutes: int = 15
    db_path: str = "woningmonitor.db"

    @classmethod
    def load(cls, path: str = "config.json") -> "Config":
        if not os.path.exists(path):
            return cls()
        with open(path) as f:
            data = json.load(f)
        config = cls()
        if "search" in data:
            for k, v in data["search"].items():
                if hasattr(config.search, k):
                    setattr(config.search, k, v)
        if "notifications" in data:
            for k, v in data["notifications"].items():
                if hasattr(config.notifications, k):
                    setattr(config.notifications, k, v)
        if "check_interval_minutes" in data:
            config.check_interval_minutes = data["check_interval_minutes"]
        if "db_path" in data:
            config.db_path = data["db_path"]
        return config

    def save(self, path: str = "config.json"):
        from dataclasses import asdict
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
