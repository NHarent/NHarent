#!/usr/bin/env python3
"""
Avond Review - Stuurt een overzicht van morgen's agenda, urgente taken,
en gevlagde mails. Helpt je de volgende dag voorbereiden.

Gebruik: python evening_review.py
"""

import datetime
from briefing_utils import (
    get_events_for_date, get_all_tasks, get_flagged_emails, get_free_blocks,
    format_date_nl, send_mail_via_outlook,
)


def build_review_html(
    tomorrow_events: list[dict],
    tasks: list[dict],
    flagged: list[dict],
    free_blocks: list[dict],
) -> str:
    """Genereer een iPhone-vriendelijke HTML avond review."""
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    date_str = format_date_nl(today)
    tomorrow_str = format_date_nl(tomorrow)

    # Eerste afspraak morgen
    first_note = ""
    timed = [e for e in tomorrow_events if not e["is_all_day"]]
    if timed:
        first = timed[0]
        first_note = f'<p style="margin:8px 0 0;font-size:13px;opacity:0.9;">Eerste afspraak morgen om <strong>{first["start_time"]}</strong> · {first["subject"]}</p>'

    # Agenda morgen
    agenda_section = _build_agenda_html(tomorrow_events)

    # Vrije blokken morgen
    free_section = ""
    if free_blocks:
        items = ""
        for block in free_blocks:
            hours = block["duration_min"] // 60
            mins = block["duration_min"] % 60
            dur = f"{hours}u{mins:02d}" if hours else f"{mins} min"
            items += f'<span style="display:inline-block;background:#e8f5e9;color:#2e7d32;font-size:13px;padding:4px 10px;border-radius:12px;margin:3px 4px 3px 0;">{block["start"]} – {block["end"]} ({dur})</span>'
        free_section = f"""
        <div style="background:#fff;padding:12px 16px;border-bottom:1px solid #e0e0e0;">
            <h2 style="margin:0 0 6px;font-size:14px;color:#2e7d32;">Vrije blokken morgen</h2>
            <div>{items}</div>
        </div>"""

    # Urgente taken (deadline vandaag/morgen/te laat)
    urgent = []
    other = []
    for task in tasks:
        due = task["due_date"]
        if due:
            try:
                due_date = datetime.date.fromisoformat(due)
                if due_date <= tomorrow:
                    urgent.append(task)
                    continue
            except ValueError:
                pass
        other.append(task)

    urgent_section = _build_task_list(urgent, today, "Geen urgente taken")
    other_section = _build_task_list(other[:10], today, "Geen overige taken")

    # Gevlagde mails
    flagged_section = ""
    if flagged:
        items = ""
        for mail in flagged[:5]:
            items += f"""
            <div style="padding:6px 12px;border-bottom:1px solid #eee;font-size:13px;">
                <div>{mail["subject"]}</div>
                <div style="color:#888;font-size:12px;">{mail["sender"]} · {mail["received"]}</div>
            </div>"""
        flagged_section = f"""
        <div style="background:#fff;padding:16px;border-bottom:1px solid #e0e0e0;">
            <h2 style="margin:0 0 4px;font-size:16px;color:#e65100;">Gevlagde mails ({len(flagged)})</h2>
            <div style="margin-top:8px;">{items}</div>
        </div>"""

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
            {first_note}
        </div>

        <div style="background:#fff;padding:16px;border-bottom:1px solid #e0e0e0;">
            <h2 style="margin:0 0 4px;font-size:16px;color:#4a148c;">Agenda morgen · {tomorrow_str}</h2>
            {agenda_section}
        </div>

        {free_section}

        <div style="background:#fff;padding:16px;border-bottom:1px solid #e0e0e0;">
            <h2 style="margin:0 0 4px;font-size:16px;color:#d32f2f;">Urgent (deadline vandaag/morgen)</h2>
            {urgent_section}
        </div>

        {flagged_section}

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


def _build_agenda_html(events: list[dict]) -> str:
    if not events:
        return '<p style="color:#888;padding:12px;font-size:14px;">Geen afspraken</p>'

    rows = ""
    for ev in events:
        subject = ev["subject"]
        time_str = "Hele dag" if ev["is_all_day"] else f'{ev["start_time"]} – {ev["end_time"]}'
        location = ev["location"]
        loc_html = f'<div style="color:#666;font-size:13px;">{location}</div>' if location else ""

        attendees = ev.get("attendees", [])
        att_html = ""
        if attendees:
            names = ", ".join(attendees[:4])
            if len(attendees) > 4:
                names += f" +{len(attendees) - 4}"
            att_html = f'<div style="color:#888;font-size:12px;">{names}</div>'

        rows += f"""
        <tr>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;white-space:nowrap;vertical-align:top;color:#555;font-size:14px;width:100px;">{time_str}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;vertical-align:top;">
                <div style="font-size:15px;font-weight:500;">{subject}</div>
                {loc_html}
                {att_html}
            </td>
        </tr>"""

    return f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">{rows}</table>'


def _build_task_list(tasks: list[dict], today: datetime.date, empty_msg: str) -> str:
    if not tasks:
        return f'<p style="color:#888;padding:12px;font-size:14px;">{empty_msg}</p>'

    items = ""
    for task in tasks:
        title = task["title"]
        due = task["due_date"]

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

        prio_dot = ""
        if task["priority"] == "high":
            prio_dot = '<span style="color:#d32f2f;font-weight:bold;">! </span>'

        items += f"""
        <div style="padding:6px 12px;border-bottom:1px solid #eee;font-size:14px;">
            {prio_dot}{title}{due_str}
        </div>"""

    return f'<div style="margin-top:8px;">{items}</div>'


def main():
    print("Avond Review wordt opgehaald...")

    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)

    tomorrow_events = get_events_for_date(tomorrow)
    print(f"  {len(tomorrow_events)} afspraken morgen")

    tasks = get_all_tasks()
    print(f"  {len(tasks)} openstaande taken")

    flagged = get_flagged_emails()
    print(f"  {len(flagged)} gevlagde mails")

    free_blocks = get_free_blocks(tomorrow_events)
    print(f"  {len(free_blocks)} vrije blokken morgen")

    html = build_review_html(tomorrow_events, tasks, flagged, free_blocks)

    subject = f"Avond Review – {format_date_nl(today)}"
    send_mail_via_outlook(subject, html)

    print("Klaar!")


if __name__ == "__main__":
    main()
