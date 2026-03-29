"""CLI entry point for the woningmonitor."""

import argparse
import json
import logging
import sys
from dataclasses import asdict

from woningmonitor.config import Config
from woningmonitor.database import ListingDatabase
from woningmonitor.monitor import run_continuous, run_scan


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_run(args):
    """Start continuous monitoring."""
    config = Config.load(args.config)
    run_continuous(config)


def cmd_scan(args):
    """Run a single scan."""
    config = Config.load(args.config)
    db = ListingDatabase(config.db_path)
    stats = run_scan(config, db)
    print(json.dumps(stats, indent=2))
    db_stats = db.get_stats()
    print(f"\nDatabase totaal: {db_stats['total']} woningen")
    for bron, count in db_stats["per_bron"].items():
        print(f"  {bron}: {count}")
    db.close()


def cmd_init(args):
    """Create a default config file."""
    config = Config()
    config.search.plaats = args.plaats or "Amsterdam"
    config.search.straal_km = args.straal or 10
    config.search.max_prijs = args.max_prijs or 1_000_000
    config.save(args.config)
    print(f"Config aangemaakt: {args.config}")
    print(f"  Plaats: {config.search.plaats}")
    print(f"  Straal: {config.search.straal_km} km")
    print(f"  Max prijs: €{config.search.max_prijs:,}")
    print(f"\nPas het bestand aan om notificaties in te stellen (Telegram/Email/ntfy)")
    print(f"Start daarna met: python -m woningmonitor run")


def cmd_stats(args):
    """Show database statistics."""
    config = Config.load(args.config)
    db = ListingDatabase(config.db_path)
    stats = db.get_stats()
    print(f"Totaal woningen: {stats['total']}")
    for bron, count in stats["per_bron"].items():
        print(f"  {bron}: {count}")
    db.close()


def main():
    parser = argparse.ArgumentParser(
        prog="woningmonitor",
        description="Monitor alle woningen te koop in je omgeving - van Funda tot stille verkoop",
    )
    parser.add_argument("-c", "--config", default="config.json", help="Pad naar config bestand")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    subparsers = parser.add_subparsers(dest="command")

    # run command
    subparsers.add_parser("run", help="Start continue monitoring")

    # scan command
    subparsers.add_parser("scan", help="Eenmalige scan uitvoeren")

    # init command
    init_parser = subparsers.add_parser("init", help="Maak een standaard configuratie aan")
    init_parser.add_argument("--plaats", help="Zoeklocatie (bijv. Amsterdam)")
    init_parser.add_argument("--straal", type=int, help="Zoekstraal in km")
    init_parser.add_argument("--max-prijs", type=int, help="Maximale prijs in euro")

    # stats command
    subparsers.add_parser("stats", help="Toon database statistieken")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command == "run":
        cmd_run(args)
    elif args.command == "scan":
        cmd_scan(args)
    elif args.command == "init":
        cmd_init(args)
    elif args.command == "stats":
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
