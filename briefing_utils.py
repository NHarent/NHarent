#!/usr/bin/env python3
"""
Gedeelde functies voor het briefing-systeem.
AppleScript helpers, Outlook/Reminders integratie, HTML formatting.
"""

import os
import sys
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


def format_date_nl(dt: datetime.date) -> str:
    """Formatteer datum in het Nederlands."""
    dagen = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
    maanden = [
        "", "januari", "februari", "maart", "april", "mei", "juni",
        "juli", "augustus", "september", "oktober", "november", "december",
    ]
    return f"{dagen[dt.weekday()]} {dt.day} {maanden[dt.month]} {dt.year}"


def parse_date_arg(text: str) -> str:
    """Vertaal Nederlandse datumtermen naar ISO datum string."""
    today = datetime.date.today()
    text = text.lower().strip()

    if text in ("vandaag", "today"):
        return today.isoformat()
    elif text in ("morgen", "tomorrow"):
        return (today + datetime.timedelta(days=1)).isoformat()
    elif text in ("overmorgen",):
        return (today + datetime.timedelta(days=2)).isoformat()
    elif text in ("volgende week", "next week"):
        # Volgende maandag
        days_ahead = 7 - today.weekday()
        return (today + datetime.timedelta(days=days_ahead)).isoformat()
    elif text in ("vrijdag", "friday"):
        days_ahead = (4 - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return (today + datetime.timedelta(days=days_ahead)).isoformat()
    else:
        # Probeer als ISO datum te parsen
        try:
            datetime.date.fromisoformat(text)
            return text
        except ValueError:
            print(f"Onbekend datumformaat: {text}")
            return ""


# --- Outlook Agenda ---

def get_events_for_date(target_date: datetime.date) -> list[dict]:
    """Haal agenda-afspraken op voor een specifieke datum uit Outlook."""
    date_str = target_date.strftime("%Y-%m-%d")
    script = f'''
    tell application "Microsoft Outlook"
        set targetDay to date "{target_date.strftime("%A, %B %d, %Y")}"
        set time of targetDay to 0
        set nextDay to targetDay + (1 * days)

        set allEvents to every calendar event whose start time >= targetDay and start time < nextDay
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
    # Alternatieve aanpak die robuuster werkt met datums
    script = '''
    tell application "Microsoft Outlook"
        set today to current date
        set time of today to 0
        set dayOffset to ''' + str((target_date - datetime.date.today()).days) + '''
        set targetDay to today + (dayOffset * days)
        set nextDay to targetDay + (1 * days)

        set allEvents to every calendar event whose start time >= targetDay and start time < nextDay
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

    events.sort(key=lambda e: ("1" if e["is_all_day"] else "0", e["start_time"]))
    return events


# --- Outlook Taken ---

def get_outlook_tasks() -> list[dict]:
    """Haal onvoltooide taken op uit Outlook."""
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

            set output to output & tName & "|||" & tPriority & "|||" & tDueStr & "|||" & tCategory & "|||outlook" & linefeed
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
        if len(parts) >= 5:
            tasks.append({
                "title": parts[0].strip(),
                "priority": parts[1].strip(),
                "due_date": parts[2].strip(),
                "category": parts[3].strip(),
                "source": parts[4].strip(),
            })
    return tasks


# --- Apple Reminders ---

def get_apple_reminders() -> list[dict]:
    """Haal onvoltooide herinneringen op uit Apple Reminders."""
    script = '''
    tell application "Reminders"
        set output to ""
        repeat with reminderList in lists
            set listName to name of reminderList
            set openReminders to (every reminder in reminderList whose completed is false)
            repeat with r in openReminders
                set rName to name of r
                try
                    set rDue to due date of r
                    set dueY to year of rDue as text
                    set dueM to text -2 thru -1 of ("0" & (month of rDue as number) as text)
                    set dueD to text -2 thru -1 of ("0" & (day of rDue as text))
                    set rDueStr to dueY & "-" & dueM & "-" & dueD
                on error
                    set rDueStr to ""
                end try
                try
                    set rPrio to priority of r as text
                on error
                    set rPrio to "0"
                end try

                set output to output & rName & "|||" & rPrio & "|||" & rDueStr & "|||" & listName & "|||reminders" & linefeed
            end repeat
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
        if len(parts) >= 5:
            # Apple Reminders priority: 0=geen, 1-4=hoog, 5=medium, 6-9=laag
            prio_raw = parts[1].strip()
            if prio_raw in ("1", "2", "3", "4"):
                priority = "priority high"
            elif prio_raw == "5":
                priority = "priority normal"
            elif prio_raw in ("6", "7", "8", "9"):
                priority = "priority low"
            else:
                priority = "priority normal"

            tasks.append({
                "title": parts[0].strip(),
                "priority": priority,
                "due_date": parts[2].strip(),
                "category": parts[3].strip(),
                "source": parts[4].strip(),
            })
    return tasks


def get_all_tasks() -> list[dict]:
    """Haal taken op uit zowel Outlook als Apple Reminders, gesorteerd."""
    tasks = get_outlook_tasks() + get_apple_reminders()

    priority_order = {"priority high": 0, "priority normal": 1, "priority low": 2}
    tasks.sort(key=lambda t: (
        priority_order.get(t["priority"], 1),
        t["due_date"] if t["due_date"] else "9999-99-99",
    ))
    return tasks


# --- Outlook Taken aanmaken ---

def create_outlook_task(title: str, due_date: str = "", priority: str = "normal") -> bool:
    """Maak een nieuwe taak aan in Outlook via AppleScript."""
    prio_map = {"hoog": "priority high", "high": "priority high",
                "normaal": "priority normal", "normal": "priority normal",
                "laag": "priority low", "low": "priority low"}
    outlook_prio = prio_map.get(priority.lower(), "priority normal")

    props = f'name:"{title}", priority:{outlook_prio}'
    if due_date:
        # AppleScript datum instellen via extra commando
        script = f'''
        tell application "Microsoft Outlook"
            set newTask to make new task with properties {{{props}}}
            set taskDue to current date
            set year of taskDue to {due_date[:4]}
            set month of taskDue to {int(due_date[5:7])}
            set day of taskDue to {int(due_date[8:10])}
            set time of taskDue to 0
            set due date of newTask to taskDue
        end tell
        '''
    else:
        script = f'''
        tell application "Microsoft Outlook"
            make new task with properties {{{props}}}
        end tell
        '''

    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f"Fout bij aanmaken taak: {result.stderr.strip()}")
        return False
    return True


# --- Mail versturen ---

def send_mail_via_outlook(subject: str, html_content: str, to_email: str = ""):
    """Verstuur een HTML mail via Outlook."""
    email = to_email or OUTLOOK_EMAIL
    if not email:
        print("Fout: OUTLOOK_EMAIL moet ingesteld zijn in .env")
        sys.exit(1)

    html_escaped = html_content.replace("\\", "\\\\").replace('"', '\\"')

    script = f'''
    tell application "Microsoft Outlook"
        set newMsg to make new outgoing message with properties {{subject:"{subject}", content:"{html_escaped}"}}
        make new to recipient at newMsg with properties {{email address:{{address:"{email}"}}}}
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

    print(f"Mail verstuurd naar {email}")
