"""Notification system - Telegram, Email, ntfy.sh push notifications."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from woningmonitor.config import NotificationConfig
from woningmonitor.database import Listing

logger = logging.getLogger(__name__)


def format_listing(listing: Listing, label: str = "Nieuwe woning") -> str:
    """Format a listing for notification display."""
    prijs_str = f"€{listing.prijs:,.0f}".replace(",", ".") if listing.prijs else "Prijs op aanvraag"
    details = []
    if listing.oppervlakte:
        details.append(f"{listing.oppervlakte}m²")
    if listing.kamers:
        details.append(f"{listing.kamers} kamers")
    if listing.makelaar:
        details.append(f"via {listing.makelaar}")

    details_str = " | ".join(details) if details else ""

    return (
        f"🏠 {label}\n"
        f"📍 {listing.adres}"
        + (f", {listing.plaats}" if listing.plaats else "")
        + f"\n💰 {prijs_str}\n"
        + (f"📐 {details_str}\n" if details_str else "")
        + f"🔗 {listing.url}\n"
        + f"📡 Bron: {listing.source}"
    )


def format_price_change(listing: Listing, oude_prijs: int | None, nieuwe_prijs: int | None) -> str:
    oud = f"€{oude_prijs:,.0f}".replace(",", ".") if oude_prijs else "onbekend"
    nieuw = f"€{nieuwe_prijs:,.0f}".replace(",", ".") if nieuwe_prijs else "onbekend"
    return (
        f"💰 Prijswijziging!\n"
        f"📍 {listing.adres}\n"
        f"Was: {oud} → Nu: {nieuw}\n"
        f"🔗 {listing.url}"
    )


def send_telegram(config: NotificationConfig, message: str) -> bool:
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": config.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Telegram notification failed: {e}")
        return False


def send_email(config: NotificationConfig, subject: str, body: str) -> bool:
    if not config.email_smtp_host or not config.email_to:
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = config.email_from
        msg["To"] = config.email_to
        msg["Subject"] = subject

        # Create HTML body
        html_body = body.replace("\n", "<br>")
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(config.email_smtp_host, config.email_smtp_port) as server:
            server.starttls()
            server.login(config.email_from, config.email_password)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"Email notification failed: {e}")
        return False


def send_ntfy(config: NotificationConfig, title: str, message: str) -> bool:
    """Send push notification via ntfy.sh (free, no account needed)."""
    if not config.ntfy_topic:
        return False
    try:
        url = f"{config.ntfy_server}/{config.ntfy_topic}"
        resp = requests.post(url, data=message.encode("utf-8"), headers={
            "Title": title,
            "Tags": "house",
        }, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"ntfy notification failed: {e}")
        return False


def notify(config: NotificationConfig, title: str, message: str):
    """Send notification through all configured channels."""
    sent = False

    if send_telegram(config, message):
        sent = True
        logger.info("Telegram notification sent")

    if send_email(config, title, message):
        sent = True
        logger.info("Email notification sent")

    if send_ntfy(config, title, message):
        sent = True
        logger.info("ntfy notification sent")

    if not sent:
        # Fallback: print to console
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
        print(message)
        print(f"{'='*60}\n")
