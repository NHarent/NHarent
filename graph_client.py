"""
Microsoft Graph API client voor Outlook, Agenda en To Do.

Gebruikt MSAL device-code flow voor authenticatie (geen server nodig).
Alle data wordt opgehaald via de Microsoft Graph REST API.
"""

import json
import logging
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

import msal
import requests

from config import GraphConfig, TOKEN_CACHE

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class GraphClient:
    """Client voor Microsoft Graph API met automatische token-refresh."""

    def __init__(self, config: GraphConfig):
        self.config = config
        self._token: str | None = None

        # MSAL cache voor token persistence
        self._cache = msal.SerializableTokenCache()
        if TOKEN_CACHE.exists():
            self._cache.deserialize(TOKEN_CACHE.read_text())

        self._app = msal.PublicClientApplication(
            client_id=config.client_id,
            authority=f"https://login.microsoftonline.com/{config.tenant_id}",
            token_cache=self._cache,
        )

    # ------------------------------------------------------------------
    # Authenticatie
    # ------------------------------------------------------------------

    def authenticate(self) -> bool:
        """Authenticeer via device-code flow of cached token."""
        accounts = self._app.get_accounts()

        if accounts:
            result = self._app.acquire_token_silent(
                scopes=self.config.scopes,
                account=accounts[0],
            )
            if result and "access_token" in result:
                self._token = result["access_token"]
                self._save_cache()
                logger.info("Ingelogd via cached token")
                return True

        # Device code flow — gebruiker logt in via browser
        flow = self._app.initiate_device_flow(scopes=self.config.scopes)
        if "user_code" not in flow:
            logger.error("Device flow mislukt: %s", flow)
            return False

        print(f"\n🔐 Open {flow['verification_uri']} en voer code in: "
              f"{flow['user_code']}\n")

        try:
            webbrowser.open(flow["verification_uri"])
        except Exception:
            pass

        result = self._app.acquire_token_by_device_flow(flow)

        if "access_token" in result:
            self._token = result["access_token"]
            self._save_cache()
            logger.info("Succesvol ingelogd via device flow")
            return True

        logger.error("Authenticatie mislukt: %s",
                      result.get("error_description", "onbekend"))
        return False

    # ------------------------------------------------------------------
    # Mail
    # ------------------------------------------------------------------

    def get_recent_mail(self, count: int = 20) -> list[dict]:
        """Haal recente e-mails op uit inbox."""
        params = {
            "$top": count,
            "$select": "id,subject,from,receivedDateTime,bodyPreview,"
                       "importance,isRead,hasAttachments",
            "$orderby": "receivedDateTime desc",
            "$filter": "isRead eq false",
        }
        data = self._get("/me/messages", params=params)
        mails = data.get("value", [])
        logger.info("%d ongelezen e-mails opgehaald", len(mails))
        return mails

    def get_mail_body(self, mail_id: str) -> str:
        """Haal de volledige body van een e-mail op."""
        data = self._get(f"/me/messages/{mail_id}",
                         params={"$select": "body"})
        return data.get("body", {}).get("content", "")

    # ------------------------------------------------------------------
    # Agenda
    # ------------------------------------------------------------------

    def get_upcoming_events(self, days_ahead: int = 7) -> list[dict]:
        """Haal agenda-events op voor de komende dagen."""
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)

        params = {
            "startDateTime": now.isoformat(),
            "endDateTime": end.isoformat(),
            "$select": "id,subject,start,end,location,organizer,"
                       "bodyPreview,attendees,isOnlineMeeting",
            "$orderby": "start/dateTime",
            "$top": 50,
        }
        data = self._get("/me/calendarView", params=params)
        events = data.get("value", [])
        logger.info("%d events gevonden in de komende %d dagen",
                     len(events), days_ahead)
        return events

    # ------------------------------------------------------------------
    # To Do (taken)
    # ------------------------------------------------------------------

    def get_or_create_task_list(self, name: str) -> str:
        """Haal takenlijst op of maak een nieuwe aan. Retourneert list ID."""
        data = self._get("/me/todo/lists")
        for lst in data.get("value", []):
            if lst["displayName"] == name:
                logger.info("Takenlijst '%s' gevonden (id=%s)",
                             name, lst["id"])
                return lst["id"]

        # Aanmaken
        new_list = self._post("/me/todo/lists",
                              json={"displayName": name})
        list_id = new_list["id"]
        logger.info("Takenlijst '%s' aangemaakt (id=%s)", name, list_id)
        return list_id

    def get_tasks(self, list_id: str) -> list[dict]:
        """Haal alle open taken op uit een lijst."""
        params = {
            "$filter": "status ne 'completed'",
            "$orderby": "importance desc,createdDateTime desc",
            "$top": 100,
        }
        data = self._get(f"/me/todo/lists/{list_id}/tasks", params=params)
        return data.get("value", [])

    def create_task(
        self,
        list_id: str,
        title: str,
        body: str = "",
        due_date: str | None = None,
        importance: str = "normal",
    ) -> dict:
        """Maak een nieuwe taak aan in Microsoft To Do.

        Args:
            list_id: ID van de takenlijst
            title: Titel van de taak
            body: Optionele beschrijving
            due_date: Deadline in YYYY-MM-DD formaat
            importance: low / normal / high
        """
        task_data: dict = {
            "title": title,
            "importance": importance,
        }

        if body:
            task_data["body"] = {
                "content": body,
                "contentType": "text",
            }

        if due_date:
            task_data["dueDateTime"] = {
                "dateTime": f"{due_date}T00:00:00",
                "timeZone": "Europe/Amsterdam",
            }

        result = self._post(
            f"/me/todo/lists/{list_id}/tasks",
            json=task_data,
        )
        logger.info("Taak aangemaakt: %s", title)
        return result

    def complete_task(self, list_id: str, task_id: str) -> None:
        """Markeer een taak als voltooid."""
        self._patch(
            f"/me/todo/lists/{list_id}/tasks/{task_id}",
            json={"status": "completed"},
        )
        logger.info("Taak %s voltooid", task_id)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        if not self._token:
            raise RuntimeError("Niet geauthenticeerd. Roep authenticate() aan.")
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{GRAPH_BASE}{path}"
        resp = requests.get(url, headers=self._headers(), params=params,
                            timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json: dict | None = None) -> dict:
        url = f"{GRAPH_BASE}{path}"
        resp = requests.post(url, headers=self._headers(), json=json,
                             timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, json: dict | None = None) -> dict:
        url = f"{GRAPH_BASE}{path}"
        resp = requests.patch(url, headers=self._headers(), json=json,
                              timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _save_cache(self) -> None:
        TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE.write_text(self._cache.serialize())
