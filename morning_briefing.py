#!/usr/bin/env python3
"""
Ochtend Briefing - Leest Outlook agenda en taken direct van je Mac via AppleScript
en stuurt een briefing mail naar jezelf. Geen Azure of API keys nodig.

Vereist: macOS met Microsoft Outlook geinstalleerd en ingelogd.
Configuratie via .env bestand of environment variabelen.
"""

import os
import sys
import json
import subprocess
import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv(Path(__file__).parent / ".env")

OUTLOOK_EMAIL = os.environ.get("OUTLOOK_EMAIL", "")


def run_applescript(script: str) -> str:
    """Voer een AppleScript uit en geef het resultaat terug."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f"AppleScript fout: {result.stderr.strip()}")
        return ""
    return result.stdout.strip()


def get_todays_events() -> list[dict]:
    """Haal agenda-afspraken van vandaag op uit Outlook via AppleScript."""
    script = '''
    tell application "Microsoft Outlook"
        set today to current date
        set time of today to 0
        set tomorrow to today + (1 * days)

        set allEvents to every calendar event whose start time >= today and start time < tomorrow
        set output to ""

        repeat with evt in allEvents
            set evtSubject to subject of evt
            set evtStart to start time of evt
            set evtEnd to end time of evt
            set evtAllDay to is all day event of evt
            try
                set evtLocation to location of evt
            on error
                set evtLocation to ""
            end try

            set startH to text -2 thru -1 of ("0" & (hours of evtStart as text))
            set startM to text -2 thru -1 of ("0" & (minutes of evtStart as text))
            set endH to text -2 thru -1 of ("0" & (hours of evtEnd as text))
            set endM to text -2 thru -1 of ("0" & (minutes of evtEnd as text))

            set output to output & evtSubject & "|||" & startH & ":" & startM & "|||" & endH & ":" & endM & "|||" & evtAllDay & "|||" & evtLocation & linefeed
        end repeat

        return output
    end tell
    '''
    raw = run_applescript(script)
    if not raw:
        return []

    events = []
    for line in raw.strip().split("\n"):
        parts = line.split("|||")
        if len(parts) >= 5:
            events.append({
                "subject": parts[0].strip(),
                "start_time": parts[1].strip(),
                "end_time": parts[2].strip(),
                "is_all_day": parts[3].strip().lower() == "true",
                "location": parts[4].strip(),
            })

    # Sorteer op starttijd
    events.sort(key=lambda e: ("1" if e["is_all_day"] else "0", e["start_time"]))
    return events


def get_flagged_tasks() -> list[dict]:
    """Haal gevlagde/onvoltooide taken op uit Outlook via AppleScript."""
    script = '''
    tell application "Microsoft Outlook"
        set allTasks to every task whose completed is false
        set output to ""

        repeat with t in allTasks
            set tName to name of t
            set tPriority to priority of t as text
            try
                set tDue to due date of t
                set dueY to year of tDue as text
                set dueM to text -2 thru -1 of ("0" & (month of tDue as number) as text)
                set dueD to text -2 thru -1 of ("0" & (day of tDue as text))
                set tDueStr to dueY & "-" & dueM & "-" & dueD
            on error
                set tDueStr to ""
            end try
            try
                set tCategory to name of first category of t
            on error
                set tCategory to ""
            end try

            set output to output & tName & "|||" & tPriority & "|||" & tDueStr & "|||" & tCategory & linefeed
        end repeat

        return output
    end tell
    '''
    raw = run_applescript(script)
    if not raw:
        return []

    tasks = []
    for line in raw.strip().split("\n"):
        parts = line.split("|||")
        if len(parts) >= 4:
            tasks.append({
                "title": parts[0].strip(),
                "priority": parts[1].strip(),
                "due_date": parts[2].strip(),
                "category": parts[3].strip(),
            })

    # Sorteer: hoge prioriteit eerst, dan op deadline
    priority_order = {"priority high": 0, "priority normal": 1, "priority low": 2}
    tasks.sort(key=lambda t: (
        priority_order.get(t["priority"], 1),
        t["due_date"] if t["due_date"] else "9999-99-99",
    ))
    return tasks


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
            subject = ev["subject"] or "(geen onderwerp)"

            if ev["is_all_day"]:
                time_str = "Hele dag"
            else:
                time_str = f'{ev["start_time"]} – {ev["end_time"]}'

            location = ev["location"]
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
            title = task["title"] or "(geen titel)"
            priority = task["priority"]
            due = task["due_date"]
            category = task["category"]

            due_str = ""
            if due:
                try:
                    due_date = datetime.date.fromisoformat(due)
                    if due_date == today:
                        due_str = '<span style="color:#d32f2f;font-size:12px;"> (vandaag)</span>'
                    elif due_date < today:
                        due_str = '<span style="color:#d32f2f;font-size:12px;font-weight:bold;"> (te laat!)</span>'
                    else:
                        due_str = f'<span style="color:#666;font-size:12px;"> ({due_date.strftime("%d/%m")})</span>'
                except ValueError:
                    pass

            priority_dot = ""
            if priority == "priority high":
                priority_dot = '<span style="color:#d32f2f;font-weight:bold;">! </span>'

            cat_badge = ""
            if category:
                cat_badge = f'<span style="background:#e3f2fd;color:#1565c0;font-size:11px;padding:1px 6px;border-radius:8px;margin-left:6px;">{category}</span>'

            task_items += f"""
            <div style="padding:8px 12px;border-bottom:1px solid #eee;font-size:15px;">
                {priority_dot}{title}{due_str}{cat_badge}
            </div>"""

        tasks_section = f'<div style="margin-top:8px;">{task_items}</div>'
    else:
        tasks_section = '<p style="color:#888;padding:12px;font-size:14px;">Geen openstaande taken</p>'

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <div style="max-width:600px;margin:0 auto;padding:16px;">
        <div style="background:linear-gradient(135deg,#1565c0,#0d47a1);color:#fff;padding:20px 16px;border-radius:12px 12px 0 0;">
            <h1 style="margin:0;font-size:22px;font-weight:600;">Goedemorgen</h1>
            <p style="margin:4px 0 0;font-size:14px;opacity:0.9;">{date_str}</p>
        </div>
        <div style="background:#fff;padding:16px;border-bottom:1px solid #e0e0e0;">
            <h2 style="margin:0 0 4px;font-size:16px;color:#1565c0;">Agenda vandaag</h2>
            {agenda_section}
        </div>
        <div style="background:#fff;padding:16px;border-radius:0 0 12px 12px;">
            <h2 style="margin:0 0 4px;font-size:16px;color:#1565c0;">Openstaande taken</h2>
            {tasks_section}
        </div>
        <p style="text-align:center;color:#999;font-size:12px;margin-top:16px;">
            Automatische briefing
        </p>
    </div>
</body>
</html>"""
    return html


def send_briefing_via_outlook(html_content: str):
    """Maak en verstuur de briefing mail via Outlook zelf."""
    if not OUTLOOK_EMAIL:
        print("Fout: OUTLOOK_EMAIL moet ingesteld zijn in .env")
        sys.exit(1)

    today = format_date_nl(datetime.date.today())
    subject = f"Ochtend Briefing – {today}"

    # Escape voor AppleScript
    html_escaped = html_content.replace("\\", "\\\\").replace('"', '\\"')

    script = f'''
    tell application "Microsoft Outlook"
        set newMsg to make new outgoing message with properties {{subject:"{subject}", content:"{html_escaped}"}}
        make new to recipient at newMsg with properties {{email address:{{address:"{OUTLOOK_EMAIL}"}}}}
        send newMsg
    end tell
    '''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f"Fout bij verzenden: {result.stderr.strip()}")
        sys.exit(1)

    print(f"Briefing verstuurd naar {OUTLOOK_EMAIL}")


def main():
    print("Ochtend Briefing wordt opgehaald...")

    events = get_todays_events()
    print(f"  {len(events)} agenda-afspraken gevonden")

    tasks = get_flagged_tasks()
    print(f"  {len(tasks)} openstaande taken gevonden")

    html = build_briefing_html(events, tasks)
    send_briefing_via_outlook(html)

    print("Klaar!")


if __name__ == "__main__":
    main()
