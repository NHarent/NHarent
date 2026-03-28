#!/usr/bin/env python3
"""
Ochtend Briefing - Leest Outlook agenda, Outlook taken en Apple Reminders
van je Mac en stuurt een iPhone-geoptimaliseerde briefing mail.

Gebruik: python morning_briefing.py
"""

import datetime
from briefing_utils import (
    get_events_for_date, get_all_tasks, format_date_nl, send_mail_via_outlook,
)


def build_briefing_html(events: list[dict], tasks: list[dict]) -> str:
    """Genereer een iPhone-vriendelijke HTML ochtend briefing."""
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
            loc_html = f'<div style="color:#666;font-size:13px;">{location}</div>' if location else ""

            agenda_rows += f"""
            <tr>
                <td style="padding:8px 12px;border-bottom:1px solid #eee;white-space:nowrap;vertical-align:top;color:#555;font-size:14px;width:100px;">{time_str}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #eee;vertical-align:top;">
                    <div style="font-size:15px;font-weight:500;">{subject}</div>
                    {loc_html}
                </td>
            </tr>"""

        agenda_section = f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">{agenda_rows}</table>'
    else:
        agenda_section = '<p style="color:#888;padding:12px;font-size:14px;">Geen afspraken vandaag</p>'

    # Taken sectie
    tasks_section = _build_tasks_html(tasks, today)

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
            Automatische ochtend briefing
        </p>
    </div>
</body>
</html>"""
    return html


def _build_tasks_html(tasks: list[dict], today: datetime.date) -> str:
    """Bouw HTML voor de taken sectie."""
    if not tasks:
        return '<p style="color:#888;padding:12px;font-size:14px;">Geen openstaande taken</p>'

    task_items = ""
    for task in tasks:
        title = task["title"] or "(geen titel)"
        priority = task["priority"]
        due = task["due_date"]
        category = task["category"]
        source = task.get("source", "")

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

        # Bron-badge: Outlook of Reminders
        source_icon = ""
        if source == "reminders":
            source_icon = '<span style="background:#fff3e0;color:#e65100;font-size:10px;padding:1px 5px;border-radius:8px;margin-left:4px;">Siri</span>'

        cat_badge = ""
        if category:
            cat_badge = f'<span style="background:#e3f2fd;color:#1565c0;font-size:11px;padding:1px 6px;border-radius:8px;margin-left:6px;">{category}</span>'

        task_items += f"""
        <div style="padding:8px 12px;border-bottom:1px solid #eee;font-size:15px;">
            {priority_dot}{title}{due_str}{cat_badge}{source_icon}
        </div>"""

    return f'<div style="margin-top:8px;">{task_items}</div>'


def main():
    print("Ochtend Briefing wordt opgehaald...")

    today = datetime.date.today()
    events = get_events_for_date(today)
    print(f"  {len(events)} agenda-afspraken gevonden")

    tasks = get_all_tasks()
    print(f"  {len(tasks)} openstaande taken gevonden (Outlook + Reminders)")

    html = build_briefing_html(events, tasks)

    subject = f"Ochtend Briefing – {format_date_nl(today)}"
    send_mail_via_outlook(subject, html)

    print("Klaar!")


if __name__ == "__main__":
    main()
