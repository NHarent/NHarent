#!/usr/bin/env python3
"""
Avond Review - Stuurt een overzicht van morgen's agenda en openstaande taken.
Helpt je de volgende dag voorbereiden.

Gebruik: python evening_review.py
"""

import datetime
from briefing_utils import (
    get_events_for_date, get_all_tasks, format_date_nl, send_mail_via_outlook,
)


def build_review_html(
    today_events: list[dict],
    tomorrow_events: list[dict],
    tasks: list[dict],
) -> str:
    """Genereer een iPhone-vriendelijke HTML avond review."""
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    date_str = format_date_nl(today)
    tomorrow_str = format_date_nl(tomorrow)

    # Samenvatting vandaag
    today_summary = f"{len(today_events)} afspraken gehad" if today_events else "Geen afspraken gehad"

    # Agenda morgen
    if tomorrow_events:
        agenda_rows = ""
        for ev in tomorrow_events:
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
        agenda_section = '<p style="color:#888;padding:12px;font-size:14px;">Geen afspraken morgen</p>'

    # Taken: filter op urgent (vandaag/te laat + morgen)
    urgent_tasks = []
    other_tasks = []
    for task in tasks:
        due = task["due_date"]
        if due:
            try:
                due_date = datetime.date.fromisoformat(due)
                if due_date <= tomorrow:
                    urgent_tasks.append(task)
                    continue
            except ValueError:
                pass
        other_tasks.append(task)

    urgent_section = _build_compact_tasks(urgent_tasks, today, "Geen urgente taken")
    other_section = _build_compact_tasks(other_tasks[:10], today, "Geen overige taken")

    # Eerste afspraak morgen
    first_event_note = ""
    if tomorrow_events:
        first = tomorrow_events[0]
        if not first["is_all_day"]:
            first_event_note = f'<p style="color:#1565c0;font-size:14px;margin:8px 0 0;">Eerste afspraak morgen om <strong>{first["start_time"]}</strong></p>'

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <div style="max-width:600px;margin:0 auto;padding:16px;">
        <div style="background:linear-gradient(135deg,#4a148c,#311b92);color:#fff;padding:20px 16px;border-radius:12px 12px 0 0;">
            <h1 style="margin:0;font-size:22px;font-weight:600;">Avond Review</h1>
            <p style="margin:4px 0 0;font-size:14px;opacity:0.9;">{date_str}</p>
            {first_event_note}
        </div>

        <div style="background:#fff;padding:16px;border-bottom:1px solid #e0e0e0;">
            <h2 style="margin:0 0 4px;font-size:16px;color:#4a148c;">Agenda morgen · {tomorrow_str}</h2>
            {agenda_section}
        </div>

        <div style="background:#fff;padding:16px;border-bottom:1px solid #e0e0e0;">
            <h2 style="margin:0 0 4px;font-size:16px;color:#d32f2f;">Urgent (deadline vandaag/morgen)</h2>
            {urgent_section}
        </div>

        <div style="background:#fff;padding:16px;border-radius:0 0 12px 12px;">
            <h2 style="margin:0 0 4px;font-size:16px;color:#4a148c;">Overige taken</h2>
            {other_section}
        </div>

        <p style="text-align:center;color:#999;font-size:12px;margin-top:16px;">
            Automatische avond review
        </p>
    </div>
</body>
</html>"""
    return html


def _build_compact_tasks(tasks: list[dict], today: datetime.date, empty_msg: str) -> str:
    """Bouw compacte HTML voor een lijst taken."""
    if not tasks:
        return f'<p style="color:#888;padding:12px;font-size:14px;">{empty_msg}</p>'

    items = ""
    for task in tasks:
        title = task["title"] or "(geen titel)"
        due = task["due_date"]
        source = task.get("source", "")

        due_str = ""
        if due:
            try:
                due_date = datetime.date.fromisoformat(due)
                if due_date < today:
                    due_str = '<span style="color:#d32f2f;font-size:12px;font-weight:bold;"> (te laat!)</span>'
                elif due_date == today:
                    due_str = '<span style="color:#d32f2f;font-size:12px;"> (vandaag)</span>'
                else:
                    due_str = f'<span style="color:#666;font-size:12px;"> ({due_date.strftime("%d/%m")})</span>'
            except ValueError:
                pass

        priority_dot = ""
        if task["priority"] == "priority high":
            priority_dot = '<span style="color:#d32f2f;font-weight:bold;">! </span>'

        source_icon = ""
        if source == "reminders":
            source_icon = '<span style="background:#fff3e0;color:#e65100;font-size:10px;padding:1px 5px;border-radius:8px;margin-left:4px;">Siri</span>'

        items += f"""
        <div style="padding:6px 12px;border-bottom:1px solid #eee;font-size:14px;">
            {priority_dot}{title}{due_str}{source_icon}
        </div>"""

    return f'<div style="margin-top:8px;">{items}</div>'


def main():
    print("Avond Review wordt opgehaald...")

    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)

    today_events = get_events_for_date(today)
    print(f"  {len(today_events)} afspraken vandaag")

    tomorrow_events = get_events_for_date(tomorrow)
    print(f"  {len(tomorrow_events)} afspraken morgen")

    tasks = get_all_tasks()
    print(f"  {len(tasks)} openstaande taken (Outlook + Reminders)")

    html = build_review_html(today_events, tomorrow_events, tasks)

    subject = f"Avond Review – {format_date_nl(today)}"
    send_mail_via_outlook(subject, html)

    print("Klaar!")


if __name__ == "__main__":
    main()
