#!/usr/bin/env python3
"""
Ochtend Briefing - Haalt Outlook agenda en taken op en stuurt een briefing mail.

Vereist Microsoft Graph API toegang via Azure AD app registratie.
Configuratie via .env bestand of environment variabelen.
"""

import os
import sys
import json
import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("Installeer requests: pip install requests")
    sys.exit(1)

try:
    from msal import ConfidentialClientApplication
except ImportError:
    print("Installeer msal: pip install msal")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("Installeer python-dotenv: pip install python-dotenv")
    sys.exit(1)

# Laad .env bestand
load_dotenv(Path(__file__).parent / ".env")

# Configuratie
AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
OUTLOOK_EMAIL = os.environ.get("OUTLOOK_EMAIL", "")
OUTLOOK_USER_ID = os.environ.get("OUTLOOK_USER_ID", "")  # Optioneel, anders wordt OUTLOOK_EMAIL gebruikt
BRIEFING_SEND_TIME = os.environ.get("BRIEFING_SEND_TIME", "07:00")  # Niet gebruikt in script zelf, voor scheduling

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["https://graph.microsoft.com/.default"]


def get_access_token() -> str:
    """Verkrijg een access token via client credentials flow."""
    if not all([AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET]):
        print("Fout: AZURE_TENANT_ID, AZURE_CLIENT_ID en AZURE_CLIENT_SECRET moeten ingesteld zijn.")
        sys.exit(1)

    authority = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}"
    app = ConfidentialClientApplication(
        AZURE_CLIENT_ID,
        authority=authority,
        client_credential=AZURE_CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=SCOPES)

    if "access_token" not in result:
        print(f"Fout bij authenticatie: {result.get('error_description', result)}")
        sys.exit(1)

    return result["access_token"]


def get_user_id(token: str) -> str:
    """Bepaal de user ID voor Graph API calls."""
    return OUTLOOK_USER_ID if OUTLOOK_USER_ID else OUTLOOK_EMAIL


def get_todays_events(token: str, user_id: str) -> list[dict]:
    """Haal de agenda-afspraken van vandaag op."""
    now = datetime.datetime.now(datetime.timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + datetime.timedelta(days=1)

    url = f"{GRAPH_BASE}/users/{user_id}/calendarView"
    params = {
        "startDateTime": start_of_day.isoformat(),
        "endDateTime": end_of_day.isoformat(),
        "$orderby": "start/dateTime",
        "$top": 50,
        "$select": "subject,start,end,location,isAllDay,organizer,bodyPreview",
    }
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        print(f"Fout bij ophalen agenda: {resp.status_code} - {resp.text}")
        return []

    return resp.json().get("value", [])


def get_todo_tasks(token: str, user_id: str) -> list[dict]:
    """Haal openstaande taken op uit Microsoft To Do."""
    headers = {"Authorization": f"Bearer {token}"}

    # Eerst alle takenlijsten ophalen
    lists_url = f"{GRAPH_BASE}/users/{user_id}/todo/lists"
    resp = requests.get(lists_url, headers=headers, timeout=30)
    if resp.status_code != 200:
        print(f"Fout bij ophalen takenlijsten: {resp.status_code} - {resp.text}")
        return []

    task_lists = resp.json().get("value", [])
    all_tasks = []

    for task_list in task_lists:
        list_id = task_list["id"]
        list_name = task_list.get("displayName", "")

        tasks_url = f"{GRAPH_BASE}/users/{user_id}/todo/lists/{list_id}/tasks"
        params = {
            "$filter": "status ne 'completed'",
            "$orderby": "importance desc, dueDateTime/dateTime asc",
            "$top": 25,
            "$select": "title,importance,dueDateTime,status,body",
        }
        resp = requests.get(tasks_url, headers=headers, params=params, timeout=30)
        if resp.status_code == 200:
            tasks = resp.json().get("value", [])
            for task in tasks:
                task["_listName"] = list_name
            all_tasks.extend(tasks)

    return all_tasks


def format_time(iso_str: str) -> str:
    """Formatteer ISO tijdstip naar HH:MM."""
    try:
        dt = datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        # Converteer naar lokale tijd (CET/CEST)
        local = dt.astimezone()
        return local.strftime("%H:%M")
    except (ValueError, AttributeError):
        return ""


def format_date_nl(dt: datetime.date) -> str:
    """Formatteer datum in het Nederlands."""
    dagen = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
    maanden = [
        "", "januari", "februari", "maart", "april", "mei", "juni",
        "juli", "augustus", "september", "oktober", "november", "december",
    ]
    return f"{dagen[dt.weekday()]} {dt.day} {maanden[dt.month]} {dt.year}"


def build_briefing_html(events: list[dict], tasks: list[dict]) -> str:
    """Genereer een iPhone-vriendelijke HTML briefing."""
    today = datetime.date.today()
    date_str = format_date_nl(today)

    # Agenda sectie
    if events:
        agenda_rows = ""
        for ev in events:
            subject = ev.get("subject", "(geen onderwerp)")
            is_all_day = ev.get("isAllDay", False)

            if is_all_day:
                time_str = "Hele dag"
            else:
                start = format_time(ev.get("start", {}).get("dateTime", ""))
                end = format_time(ev.get("end", {}).get("dateTime", ""))
                time_str = f"{start} – {end}" if start and end else ""

            location = ev.get("location", {}).get("displayName", "")
            location_html = f'<div style="color:#666;font-size:13px;">{location}</div>' if location else ""

            agenda_rows += f"""
            <tr>
                <td style="padding:8px 12px;border-bottom:1px solid #eee;white-space:nowrap;vertical-align:top;color:#555;font-size:14px;width:100px;">{time_str}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #eee;vertical-align:top;">
                    <div style="font-size:15px;font-weight:500;">{subject}</div>
                    {location_html}
                </td>
            </tr>"""

        agenda_section = f"""
        <table style="width:100%;border-collapse:collapse;margin-top:8px;">
            {agenda_rows}
        </table>"""
    else:
        agenda_section = '<p style="color:#888;padding:12px;font-size:14px;">Geen afspraken vandaag</p>'

    # Taken sectie
    if tasks:
        task_items = ""
        for task in tasks:
            title = task.get("title", "(geen titel)")
            importance = task.get("importance", "normal")
            list_name = task.get("_listName", "")
            due = task.get("dueDateTime", {})
            due_str = ""
            if due and due.get("dateTime"):
                try:
                    due_date = datetime.date.fromisoformat(due["dateTime"][:10])
                    if due_date == today:
                        due_str = '<span style="color:#d32f2f;font-size:12px;"> (vandaag)</span>'
                    elif due_date < today:
                        due_str = '<span style="color:#d32f2f;font-size:12px;font-weight:bold;"> (te laat!)</span>'
                    else:
                        due_str = f'<span style="color:#666;font-size:12px;"> ({due_date.strftime("%d/%m")})</span>'
                except ValueError:
                    pass

            priority_dot = ""
            if importance == "high":
                priority_dot = '<span style="color:#d32f2f;font-weight:bold;">● </span>'

            list_badge = ""
            if list_name:
                list_badge = f'<span style="background:#e3f2fd;color:#1565c0;font-size:11px;padding:1px 6px;border-radius:8px;margin-left:6px;">{list_name}</span>'

            task_items += f"""
            <div style="padding:8px 12px;border-bottom:1px solid #eee;font-size:15px;">
                {priority_dot}{title}{due_str}{list_badge}
            </div>"""

        tasks_section = f'<div style="margin-top:8px;">{task_items}</div>'
    else:
        tasks_section = '<p style="color:#888;padding:12px;font-size:14px;">Geen openstaande taken</p>'

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ochtend Briefing</title>
</head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <div style="max-width:600px;margin:0 auto;padding:16px;">

        <!-- Header -->
        <div style="background:linear-gradient(135deg,#1565c0,#0d47a1);color:#fff;padding:20px 16px;border-radius:12px 12px 0 0;">
            <h1 style="margin:0;font-size:22px;font-weight:600;">Goedemorgen</h1>
            <p style="margin:4px 0 0;font-size:14px;opacity:0.9;">{date_str}</p>
        </div>

        <!-- Agenda -->
        <div style="background:#fff;padding:16px;border-bottom:1px solid #e0e0e0;">
            <h2 style="margin:0 0 4px;font-size:16px;color:#1565c0;">📅 Agenda vandaag</h2>
            {agenda_section}
        </div>

        <!-- Taken -->
        <div style="background:#fff;padding:16px;border-radius:0 0 12px 12px;">
            <h2 style="margin:0 0 4px;font-size:16px;color:#1565c0;">✅ Openstaande taken</h2>
            {tasks_section}
        </div>

        <!-- Footer -->
        <p style="text-align:center;color:#999;font-size:12px;margin-top:16px;">
            Automatische briefing · {datetime.datetime.now().strftime("%H:%M")}
        </p>
    </div>
</body>
</html>"""

    return html


def send_briefing_email(token: str, user_id: str, html_content: str):
    """Verstuur de briefing als e-mail via Graph API."""
    if not OUTLOOK_EMAIL:
        print("Fout: OUTLOOK_EMAIL moet ingesteld zijn.")
        sys.exit(1)

    today = format_date_nl(datetime.date.today())
    url = f"{GRAPH_BASE}/users/{user_id}/sendMail"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    mail_body = {
        "message": {
            "subject": f"Ochtend Briefing – {today}",
            "body": {
                "contentType": "HTML",
                "content": html_content,
            },
            "toRecipients": [
                {"emailAddress": {"address": OUTLOOK_EMAIL}}
            ],
        },
        "saveToSentItems": "false",
    }

    resp = requests.post(url, headers=headers, json=mail_body, timeout=30)
    if resp.status_code == 202:
        print(f"Briefing verstuurd naar {OUTLOOK_EMAIL}")
    else:
        print(f"Fout bij verzenden: {resp.status_code} - {resp.text}")
        sys.exit(1)


def main():
    print("Ochtend Briefing wordt opgehaald...")

    token = get_access_token()
    user_id = get_user_id(token)

    events = get_todays_events(token, user_id)
    print(f"  {len(events)} agenda-afspraken gevonden")

    tasks = get_todo_tasks(token, user_id)
    print(f"  {len(tasks)} openstaande taken gevonden")

    html = build_briefing_html(events, tasks)

    send_briefing_email(token, user_id, html)
    print("Klaar!")


if __name__ == "__main__":
    main()
