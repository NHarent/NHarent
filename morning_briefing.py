#!/usr/bin/env python3
"""
Ochtend Briefing - Leest Outlook agenda, taken, gevlagde mails en ongelezen
mails direct van je Windows PC en stuurt een iPhone-geoptimaliseerde briefing.

Gebruik: python morning_briefing.py
Vereist: Windows met Outlook geinstalleerd en ingelogd + pywin32
"""

import datetime
from briefing_utils import (
    get_events_for_date, get_all_tasks, get_flagged_emails, get_unread_summary,
    get_free_blocks, format_date_nl, send_mail_via_outlook,
)


def build_briefing_html(
    events: list[dict],
    tasks: list[dict],
    flagged: list[dict],
    unread: dict,
    free_blocks: list[dict],
) -> str:
    """Genereer een iPhone-vriendelijke HTML ochtend briefing."""
    today = datetime.date.today()
    date_str = format_date_nl(today)

    # Snelle samenvatting bovenin
    n_events = len([e for e in events if not e["is_all_day"]])
    n_tasks = len(tasks)
    n_unread = unread["total"]
    n_flagged = len(flagged)

    summary_parts = []
    if n_events:
        summary_parts.append(f"{n_events} afspraken")
    if n_tasks:
        summary_parts.append(f"{n_tasks} taken")
    if n_unread:
        summary_parts.append(f"{n_unread} ongelezen mails")
    summary_text = " · ".join(summary_parts) if summary_parts else "Rustige dag"

    # Vrije blokken tekst
    free_text = ""
    if free_blocks:
        biggest = max(free_blocks, key=lambda b: b["duration_min"])
        hours = biggest["duration_min"] // 60
        mins = biggest["duration_min"] % 60
        dur = f"{hours}u{mins:02d}" if hours else f"{mins} min"
        free_text = f'<p style="margin:8px 0 0;font-size:13px;opacity:0.9;">Langste vrij blok: {biggest["start"]} – {biggest["end"]} ({dur})</p>'

    # Agenda sectie
    agenda_section = _build_agenda_html(events)

    # Taken sectie
    tasks_section = _build_tasks_html(tasks, today)

    # Mail sectie
    mail_section = _build_mail_html(flagged, unread)

    # Vrije blokken sectie
    free_section = _build_free_blocks_html(free_blocks)

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
            <p style="margin:6px 0 0;font-size:13px;opacity:0.8;">{summary_text}</p>
            {free_text}
        </div>

        <div style="background:#fff;padding:16px;border-bottom:1px solid #e0e0e0;">
            <h2 style="margin:0 0 4px;font-size:16px;color:#1565c0;">Agenda vandaag</h2>
            {agenda_section}
        </div>

        {free_section}

        <div style="background:#fff;padding:16px;border-bottom:1px solid #e0e0e0;">
            <h2 style="margin:0 0 4px;font-size:16px;color:#1565c0;">Openstaande taken</h2>
            {tasks_section}
        </div>

        <div style="background:#fff;padding:16px;border-radius:0 0 12px 12px;">
            <h2 style="margin:0 0 4px;font-size:16px;color:#1565c0;">Mail</h2>
            {mail_section}
        </div>

        <p style="text-align:center;color:#999;font-size:12px;margin-top:16px;">
            Automatische ochtend briefing
        </p>
    </div>
</body>
</html>"""
    return html


def _build_agenda_html(events: list[dict]) -> str:
    if not events:
        return '<p style="color:#888;padding:12px;font-size:14px;">Geen afspraken vandaag</p>'

    rows = ""
    for ev in events:
        subject = ev["subject"]
        if ev["is_all_day"]:
            time_str = "Hele dag"
        else:
            time_str = f'{ev["start_time"]} – {ev["end_time"]}'

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


def _build_tasks_html(tasks: list[dict], today: datetime.date) -> str:
    if not tasks:
        return '<p style="color:#888;padding:12px;font-size:14px;">Geen openstaande taken</p>'

    items = ""
    for task in tasks[:15]:  # Max 15 in briefing
        title = task["title"]
        due = task["due_date"]

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

        prio_dot = ""
        if task["priority"] == "high":
            prio_dot = '<span style="color:#d32f2f;font-weight:bold;">! </span>'

        cat = task["category"]
        cat_html = f'<span style="background:#e3f2fd;color:#1565c0;font-size:11px;padding:1px 6px;border-radius:8px;margin-left:6px;">{cat}</span>' if cat else ""

        items += f"""
        <div style="padding:8px 12px;border-bottom:1px solid #eee;font-size:15px;">
            {prio_dot}{title}{due_str}{cat_html}
        </div>"""

    extra = len(tasks) - 15
    if extra > 0:
        items += f'<div style="padding:8px 12px;color:#888;font-size:13px;">+{extra} meer taken</div>'

    return f'<div style="margin-top:8px;">{items}</div>'


def _build_mail_html(flagged: list[dict], unread: dict) -> str:
    parts = ""

    # Ongelezen samenvatting
    if unread["total"] > 0:
        parts += f'<div style="padding:8px 12px;font-size:14px;color:#555;border-bottom:1px solid #eee;"><strong>{unread["total"]}</strong> ongelezen mails'
        if unread["top_senders"]:
            top = ", ".join(f"{name} ({n})" for name, n in unread["top_senders"][:3])
            parts += f'<div style="font-size:12px;color:#888;margin-top:2px;">Meeste van: {top}</div>'
        parts += '</div>'
    else:
        parts += '<div style="padding:8px 12px;font-size:14px;color:#888;">Geen ongelezen mails</div>'

    # Gevlagde mails
    if flagged:
        parts += f'<div style="padding:8px 12px;font-size:14px;font-weight:500;color:#e65100;border-bottom:1px solid #eee;">Gevlagd voor opvolging ({len(flagged)})</div>'
        for mail in flagged[:5]:
            parts += f"""
            <div style="padding:6px 12px;border-bottom:1px solid #eee;font-size:13px;">
                <div>{mail["subject"]}</div>
                <div style="color:#888;font-size:12px;">{mail["sender"]} · {mail["received"]}</div>
            </div>"""
        if len(flagged) > 5:
            parts += f'<div style="padding:6px 12px;color:#888;font-size:12px;">+{len(flagged) - 5} meer</div>'

    return f'<div style="margin-top:8px;">{parts}</div>'


def _build_free_blocks_html(free_blocks: list[dict]) -> str:
    if not free_blocks:
        return ""

    items = ""
    for block in free_blocks:
        hours = block["duration_min"] // 60
        mins = block["duration_min"] % 60
        dur = f"{hours}u{mins:02d}" if hours else f"{mins} min"
        items += f'<span style="display:inline-block;background:#e8f5e9;color:#2e7d32;font-size:13px;padding:4px 10px;border-radius:12px;margin:3px 4px 3px 0;">{block["start"]} – {block["end"]} ({dur})</span>'

    return f"""
    <div style="background:#fff;padding:12px 16px;border-bottom:1px solid #e0e0e0;">
        <h2 style="margin:0 0 6px;font-size:14px;color:#2e7d32;">Vrije blokken</h2>
        <div>{items}</div>
    </div>"""


def main():
    print("Ochtend Briefing wordt opgehaald...")

    today = datetime.date.today()

    events = get_events_for_date(today)
    print(f"  {len(events)} agenda-afspraken")

    tasks = get_all_tasks()
    print(f"  {len(tasks)} openstaande taken")

    flagged = get_flagged_emails()
    print(f"  {len(flagged)} gevlagde mails")

    unread = get_unread_summary()
    print(f"  {unread['total']} ongelezen mails")

    free_blocks = get_free_blocks(events)
    print(f"  {len(free_blocks)} vrije blokken")

    html = build_briefing_html(events, tasks, flagged, unread, free_blocks)

    subject = f"Ochtend Briefing – {format_date_nl(today)}"
    send_mail_via_outlook(subject, html)

    print("Klaar!")


if __name__ == "__main__":
    main()
