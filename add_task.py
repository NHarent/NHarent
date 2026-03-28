#!/usr/bin/env python3
"""
Quick-capture: voeg snel een taak toe aan Outlook vanaf de terminal.

Gebruik:
  python add_task.py "Bel Jan over project X"
  python add_task.py "Offerte sturen" --due morgen
  python add_task.py "Rapport afronden" --due 2026-04-01 --prio hoog
  python add_task.py "Iets kleins" --due vrijdag --prio laag
"""

import sys
import argparse
from briefing_utils import create_outlook_task, parse_date_arg


def main():
    parser = argparse.ArgumentParser(
        description="Voeg snel een taak toe aan Outlook",
        epilog="Datum opties: vandaag, morgen, overmorgen, vrijdag, volgende week, of YYYY-MM-DD",
    )
    parser.add_argument("titel", help="Naam/omschrijving van de taak")
    parser.add_argument("--due", "-d", default="", help="Deadline (bijv. morgen, vrijdag, 2026-04-01)")
    parser.add_argument("--prio", "-p", default="normaal", choices=["hoog", "normaal", "laag"],
                        help="Prioriteit (standaard: normaal)")

    args = parser.parse_args()

    due_date = ""
    if args.due:
        due_date = parse_date_arg(args.due)
        if not due_date:
            sys.exit(1)

    print(f"Taak aanmaken: {args.titel}")
    if due_date:
        print(f"  Deadline: {due_date}")
    print(f"  Prioriteit: {args.prio}")

    if create_outlook_task(args.titel, due_date, args.prio):
        print("Taak aangemaakt in Outlook!")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
