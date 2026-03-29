#!/usr/bin/env python3
"""
Gedeelde functies voor het briefing-systeem.
Detecteert automatisch het platform:
  - macOS: stuurt Outlook aan via AppleScript
  - Windows: stuurt Outlook aan via pywin32 COM
Geen Azure of API keys nodig - alleen Outlook geinstalleerd en ingelogd.
"""

import os
import sys
import platform
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
IS_MAC = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"


# ==========================================================================
# Platform helpers
# ==========================================================================

def _run_applescript(script: str) -> str:
    """Voer een AppleScript uit en geef het resultaat terug (macOS)."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        print(f"AppleScript fout: {result.stderr.strip()}")
        return ""
    return result.stdout.strip()


def _get_outlook_com():
    """Maak verbinding met Outlook via COM (Windows)."""
    try:
        import win32com.client
    except ImportError:
        print("Installeer pywin32: pip install pywin32")
        sys.exit(1)
    return win32com.client.Dispatch("Outlook.Application")


# ==========================================================================
# Datum helpers
# ==========================================================================

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

    lookup = {
        "vandaag": 0, "today": 0,
        "morgen": 1, "tomorrow": 1,
        "overmorgen": 2,
    }
    if text in lookup:
        return (today + datetime.timedelta(days=lookup[text])).isoformat()
    if text in ("volgende week", "next week"):
        days_ahead = 7 - today.weekday()
        return (today + datetime.timedelta(days=days_ahead)).isoformat()

    dag_lookup = {
        "maandag": 0, "dinsdag": 1, "woensdag": 2, "donderdag": 3,
        "vrijdag": 4, "zaterdag": 5, "zondag": 6,
    }
    if text in dag_lookup:
        target = dag_lookup[text]
        days_ahead = (target - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return (today + datetime.timedelta(days=days_ahead)).isoformat()

    try:
        datetime.date.fromisoformat(text)
        return text
    except ValueError:
        print(f"Onbekend datumformaat: {text}")
        return ""


# ==========================================================================
# Outlook Agenda
# ==========================================================================

def get_events_for_date(target_date: datetime.date) -> list[dict]:
    """Haal agenda-afspraken op voor een specifieke datum."""
    if IS_MAC:
        return _get_events_mac(target_date)
    elif IS_WINDOWS:
        return _get_events_windows(target_date)
    else:
        print(f"Platform niet ondersteund: {platform.system()}")
        return []


def _get_events_mac(target_date: datetime.date) -> list[dict]:
    day_offset = (target_date - datetime.date.today()).days
    script = f'''
    tell application "Microsoft Outlook"
        set today to current date
        set time of today to 0
        set targetDay to today + ({day_offset} * days)
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
            try
                set evtOrganizer to organizer of evt
                set orgName to display name of evtOrganizer
            on error
                set orgName to ""
            end try

            -- Deelnemers
            set attNames to ""
            try
                repeat with att in attendees of evt
                    if attNames is not "" then set attNames to attNames & ", "
                    set attNames to attNames & display name of att
                end repeat
            on error
                set attNames to ""
            end try

            set startH to text -2 thru -1 of ("0" & (hours of evtStart as text))
            set startM to text -2 thru -1 of ("0" & (minutes of evtStart as text))
            set endH to text -2 thru -1 of ("0" & (hours of evtEnd as text))
            set endM to text -2 thru -1 of ("0" & (minutes of evtEnd as text))

            set output to output & evtSubject & "|||" & startH & ":" & startM & "|||" & endH & ":" & endM & "|||" & evtAllDay & "|||" & evtLocation & "|||" & orgName & "|||" & attNames & linefeed
        end repeat
        return output
    end tell
    '''
    raw = _run_applescript(script)
    if not raw:
        return []

    events = []
    for line in raw.strip().split("\n"):
        parts = line.split("|||")
        if len(parts) >= 7:
            att_str = parts[6].strip()
            attendees = [a.strip() for a in att_str.split(",") if a.strip()] if att_str else []
            events.append({
                "subject": parts[0].strip(),
                "start_time": parts[1].strip(),
                "end_time": parts[2].strip(),
                "is_all_day": parts[3].strip().lower() == "true",
                "location": parts[4].strip(),
                "organizer": parts[5].strip(),
                "attendees": attendees,
            })

    events.sort(key=lambda e: ("1" if e["is_all_day"] else "0", e["start_time"]))
    return events


def _get_events_windows(target_date: datetime.date) -> list[dict]:
    outlook = _get_outlook_com()
    namespace = outlook.GetNamespace("MAPI")
    calendar = namespace.GetDefaultFolder(9)  # olFolderCalendar

    start = target_date.strftime("%m/%d/%Y 00:00")
    end = (target_date + datetime.timedelta(days=1)).strftime("%m/%d/%Y 00:00")

    items = calendar.Items
    items.Sort("[Start]")
    items.IncludeRecurrences = True
    filtered = items.Restrict(f"[Start] >= '{start}' AND [Start] < '{end}'")

    events = []
    for item in filtered:
        try:
            attendees = []
            try:
                for r in item.Recipients:
                    attendees.append(r.Name)
            except Exception:
                pass
            events.append({
                "subject": item.Subject or "(geen onderwerp)",
                "start_time": item.Start.strftime("%H:%M"),
                "end_time": item.End.strftime("%H:%M"),
                "is_all_day": bool(item.AllDayEvent),
                "location": item.Location or "",
                "organizer": item.Organizer or "",
                "attendees": attendees,
            })
        except Exception as e:
            print(f"  Waarschuwing: afspraak overgeslagen ({e})")

    events.sort(key=lambda e: ("1" if e["is_all_day"] else "0", e["start_time"]))
    return events


# ==========================================================================
# Outlook Taken
# ==========================================================================

def get_outlook_tasks() -> list[dict]:
    """Haal onvoltooide taken op uit Outlook."""
    if IS_MAC:
        return _get_tasks_mac()
    elif IS_WINDOWS:
        return _get_tasks_windows()
    return []


def _get_tasks_mac() -> list[dict]:
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
    raw = _run_applescript(script)
    if not raw:
        return []

    # macOS Outlook priority mapping
    mac_prio = {"priority high": "high", "priority normal": "normal", "priority low": "low"}
    tasks = []
    for line in raw.strip().split("\n"):
        parts = line.split("|||")
        if len(parts) >= 4:
            tasks.append({
                "title": parts[0].strip(),
                "priority": mac_prio.get(parts[1].strip(), "normal"),
                "due_date": parts[2].strip(),
                "category": parts[3].strip(),
                "source": "outlook",
            })
    return tasks


def _get_tasks_windows() -> list[dict]:
    outlook = _get_outlook_com()
    namespace = outlook.GetNamespace("MAPI")
    tasks_folder = namespace.GetDefaultFolder(13)  # olFolderTasks
    filtered = tasks_folder.Items.Restrict("[Complete] = False")

    prio_map = {0: "low", 1: "normal", 2: "high"}
    tasks = []
    for item in filtered:
        try:
            due_str = ""
            try:
                due = item.DueDate
                if due.year < 4000:
                    due_str = due.strftime("%Y-%m-%d")
            except Exception:
                pass
            tasks.append({
                "title": item.Subject or "(geen titel)",
                "priority": prio_map.get(item.Importance, "normal"),
                "due_date": due_str,
                "category": item.Categories or "",
                "source": "outlook",
            })
        except Exception as e:
            print(f"  Waarschuwing: taak overgeslagen ({e})")
    return tasks


def get_all_tasks() -> list[dict]:
    """Haal alle taken op, gesorteerd op prioriteit en deadline."""
    tasks = get_outlook_tasks()
    priority_order = {"high": 0, "normal": 1, "low": 2}
    tasks.sort(key=lambda t: (
        priority_order.get(t["priority"], 1),
        t["due_date"] if t["due_date"] else "9999-99-99",
    ))
    return tasks


# ==========================================================================
# Outlook Mail (lezen)
# ==========================================================================

def get_flagged_emails() -> list[dict]:
    """Haal gevlagde mails op uit Outlook inbox."""
    if IS_MAC:
        return _get_flagged_mac()
    elif IS_WINDOWS:
        return _get_flagged_windows()
    return []


def _get_flagged_mac() -> list[dict]:
    script = '''
    tell application "Microsoft Outlook"
        set flaggedMails to every message of inbox whose flagged is true
        set output to ""
        repeat with msg in flaggedMails
            set mSubject to subject of msg
            set mSender to display name of sender of msg
            set mDate to time received of msg
            set dateY to year of mDate as text
            set dateM to text -2 thru -1 of ("0" & (month of mDate as number) as text)
            set dateD to text -2 thru -1 of ("0" & (day of mDate as text))
            set dateH to text -2 thru -1 of ("0" & (hours of mDate as text))
            set dateMin to text -2 thru -1 of ("0" & (minutes of mDate as text))
            set output to output & mSubject & "|||" & mSender & "|||" & dateD & "/" & dateM & " " & dateH & ":" & dateMin & "|||" & dateY & "-" & dateM & "-" & dateD & linefeed
        end repeat
        return output
    end tell
    '''
    raw = _run_applescript(script)
    if not raw:
        return []

    emails = []
    for line in raw.strip().split("\n"):
        parts = line.split("|||")
        if len(parts) >= 4:
            emails.append({
                "subject": parts[0].strip(),
                "sender": parts[1].strip(),
                "received": parts[2].strip(),
                "received_date": parts[3].strip(),
            })

    emails.sort(key=lambda e: e["received_date"], reverse=True)
    return emails


def _get_flagged_windows() -> list[dict]:
    outlook = _get_outlook_com()
    namespace = outlook.GetNamespace("MAPI")
    inbox = namespace.GetDefaultFolder(6)  # olFolderInbox
    flagged = inbox.Items.Restrict("[FlagStatus] = 2")

    emails = []
    for item in flagged:
        try:
            emails.append({
                "subject": item.Subject or "(geen onderwerp)",
                "sender": item.SenderName or "",
                "received": item.ReceivedTime.strftime("%d/%m %H:%M"),
                "received_date": item.ReceivedTime.strftime("%Y-%m-%d"),
            })
        except Exception:
            pass

    emails.sort(key=lambda e: e["received_date"], reverse=True)
    return emails


def get_unread_summary() -> dict:
    """Haal samenvatting op van ongelezen mails."""
    if IS_MAC:
        return _get_unread_mac()
    elif IS_WINDOWS:
        return _get_unread_windows()
    return {"total": 0, "top_senders": []}


def _get_unread_mac() -> dict:
    script = '''
    tell application "Microsoft Outlook"
        set unreadMails to every message of inbox whose is read is false
        set output to ""
        repeat with msg in unreadMails
            try
                set mSender to display name of sender of msg
            on error
                set mSender to "Onbekend"
            end try
            set output to output & mSender & linefeed
        end repeat
        return output
    end tell
    '''
    raw = _run_applescript(script)
    senders = {}
    total = 0
    if raw:
        for line in raw.strip().split("\n"):
            name = line.strip()
            if name:
                total += 1
                senders[name] = senders.get(name, 0) + 1

    top = sorted(senders.items(), key=lambda x: x[1], reverse=True)[:5]
    return {"total": total, "top_senders": top}


def _get_unread_windows() -> dict:
    outlook = _get_outlook_com()
    namespace = outlook.GetNamespace("MAPI")
    inbox = namespace.GetDefaultFolder(6)
    unread = inbox.Items.Restrict("[UnRead] = True")

    total = unread.Count
    senders = {}
    for item in unread:
        try:
            sender = item.SenderName or "Onbekend"
            senders[sender] = senders.get(sender, 0) + 1
        except Exception:
            pass

    top = sorted(senders.items(), key=lambda x: x[1], reverse=True)[:5]
    return {"total": total, "top_senders": top}


# ==========================================================================
# Outlook Taken aanmaken
# ==========================================================================

def create_outlook_task(title: str, due_date: str = "", priority: str = "normal") -> bool:
    """Maak een nieuwe taak aan in Outlook."""
    if IS_MAC:
        return _create_task_mac(title, due_date, priority)
    elif IS_WINDOWS:
        return _create_task_windows(title, due_date, priority)
    print(f"Platform niet ondersteund: {platform.system()}")
    return False


def _create_task_mac(title: str, due_date: str, priority: str) -> bool:
    prio_map = {"hoog": "priority high", "high": "priority high",
                "normaal": "priority normal", "normal": "priority normal",
                "laag": "priority low", "low": "priority low"}
    outlook_prio = prio_map.get(priority.lower(), "priority normal")
    props = f'name:"{title}", priority:{outlook_prio}'

    if due_date:
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
    result = subprocess.run(["osascript", "-e", script],
                            capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"Fout bij aanmaken taak: {result.stderr.strip()}")
        return False
    return True


def _create_task_windows(title: str, due_date: str, priority: str) -> bool:
    outlook = _get_outlook_com()
    task = outlook.CreateItem(3)  # olTaskItem
    task.Subject = title
    prio_map = {"hoog": 2, "high": 2, "normaal": 1, "normal": 1, "laag": 0, "low": 0}
    task.Importance = prio_map.get(priority.lower(), 1)
    if due_date:
        task.DueDate = due_date
    try:
        task.Save()
        return True
    except Exception as e:
        print(f"Fout bij aanmaken taak: {e}")
        return False


# ==========================================================================
# Vrije blokken
# ==========================================================================

def get_free_blocks(events: list[dict], workday_start: str = "08:00",
                    workday_end: str = "17:30", min_minutes: int = 30) -> list[dict]:
    """Vind vrije blokken in de agenda tussen afspraken."""
    if not events:
        return [{"start": workday_start, "end": workday_end,
                 "duration_min": _minutes_between(workday_start, workday_end)}]

    timed = sorted(
        [e for e in events if not e["is_all_day"]],
        key=lambda e: e["start_time"],
    )

    blocks = []
    current = workday_start

    for ev in timed:
        if ev["start_time"] > current:
            duration = _minutes_between(current, ev["start_time"])
            if duration >= min_minutes:
                blocks.append({"start": current, "end": ev["start_time"],
                               "duration_min": duration})
        if ev["end_time"] > current:
            current = ev["end_time"]

    if current < workday_end:
        duration = _minutes_between(current, workday_end)
        if duration >= min_minutes:
            blocks.append({"start": current, "end": workday_end,
                           "duration_min": duration})

    return blocks


def _minutes_between(start: str, end: str) -> int:
    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    return (eh * 60 + em) - (sh * 60 + sm)


# ==========================================================================
# Mail versturen
# ==========================================================================

def send_mail_via_outlook(subject: str, html_content: str, to_email: str = ""):
    """Verstuur een HTML mail via Outlook."""
    email = to_email or OUTLOOK_EMAIL
    if not email:
        print("Fout: OUTLOOK_EMAIL moet ingesteld zijn in .env")
        sys.exit(1)

    if IS_MAC:
        _send_mail_mac(subject, html_content, email)
    elif IS_WINDOWS:
        _send_mail_windows(subject, html_content, email)
    else:
        print(f"Platform niet ondersteund: {platform.system()}")
        sys.exit(1)


def _send_mail_mac(subject: str, html_content: str, email: str):
    html_escaped = html_content.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
    tell application "Microsoft Outlook"
        set newMsg to make new outgoing message with properties {{subject:"{subject}", content:"{html_escaped}"}}
        make new to recipient at newMsg with properties {{email address:{{address:"{email}"}}}}
        send newMsg
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script],
                            capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"Fout bij verzenden: {result.stderr.strip()}")
        sys.exit(1)
    print(f"Mail verstuurd naar {email}")


def _send_mail_windows(subject: str, html_content: str, email: str):
    outlook = _get_outlook_com()
    mail = outlook.CreateItem(0)  # olMailItem
    mail.Subject = subject
    mail.HTMLBody = html_content
    mail.To = email
    try:
        mail.Send()
        print(f"Mail verstuurd naar {email}")
    except Exception as e:
        print(f"Fout bij verzenden: {e}")
        sys.exit(1)
