"""Main monitoring orchestrator - runs all scrapers and sends notifications."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from woningmonitor.config import Config
from woningmonitor.database import Listing, ListingDatabase
from woningmonitor.notifications import (
    format_listing,
    format_price_change,
    notify,
)
from woningmonitor.scrapers.funda import FundaScraper
from woningmonitor.scrapers.huislijn import HuislijnScraper
from woningmonitor.scrapers.huizenzoeker import HuizenZoekerScraper
from woningmonitor.scrapers.jaap import JaapScraper
from woningmonitor.scrapers.makelaarsland import MakelaarslandScraper
from woningmonitor.scrapers.pararius import ParariusScraper
from woningmonitor.scrapers.stille_verkoop import StilleVerkoopScraper
from woningmonitor.scrapers.zah import ZahScraper

logger = logging.getLogger(__name__)

ALL_SCRAPERS = [
    FundaScraper,
    JaapScraper,
    ParariusScraper,
    HuislijnScraper,
    ZahScraper,
    MakelaarslandScraper,
    HuizenZoekerScraper,
    StilleVerkoopScraper,
]


def run_scraper(scraper_cls, filters):
    """Run a single scraper, return (name, listings) or (name, error)."""
    scraper = scraper_cls()
    try:
        listings = scraper.scrape(filters)
        return scraper.name, listings, None
    except Exception as e:
        logger.error(f"Scraper {scraper.name} crashed: {e}")
        return scraper.name, [], e


def run_scan(config: Config, db: ListingDatabase) -> dict:
    """Run all scrapers in parallel and process results."""
    stats = {"new": 0, "updated": 0, "errors": 0, "total_found": 0}

    # Run scrapers in parallel with ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(run_scraper, cls, config.search): cls
            for cls in ALL_SCRAPERS
        }

        for future in as_completed(futures):
            name, listings, error = future.result()

            if error:
                stats["errors"] += 1
                continue

            stats["total_found"] += len(listings)

            for listing in listings:
                # Apply filters
                if not _matches_filters(listing, config.search):
                    continue

                is_new, has_changes, old = db.upsert_listing(listing)

                if is_new:
                    stats["new"] += 1
                    label = "Nieuwe woning gevonden!" if listing.source != "stille_verkoop_makelaar" \
                        else "⚡ Mogelijke stille verkoop!"
                    msg = format_listing(listing, label=label)
                    notify(config.notifications, label, msg)
                    db.mark_notified(listing.source, listing.external_id)

                elif has_changes and old:
                    stats["updated"] += 1
                    if old.prijs != listing.prijs:
                        msg = format_price_change(listing, old.prijs, listing.prijs)
                        notify(config.notifications, "Prijswijziging!", msg)

                    if old.status != listing.status:
                        msg = (
                            f"📋 Status gewijzigd: {old.status} → {listing.status}\n"
                            f"📍 {listing.adres}\n"
                            f"🔗 {listing.url}"
                        )
                        notify(config.notifications, "Status gewijzigd", msg)

    return stats


def _matches_filters(listing: Listing, filters) -> bool:
    """Check if a listing matches the search filters."""
    if listing.prijs is not None:
        if filters.min_prijs > 0 and listing.prijs < filters.min_prijs:
            return False
        if listing.prijs > filters.max_prijs:
            return False

    if listing.oppervlakte is not None and filters.min_oppervlakte > 0:
        if listing.oppervlakte < filters.min_oppervlakte:
            return False

    if listing.kamers is not None and filters.min_kamers > 0:
        if listing.kamers < filters.min_kamers:
            return False

    return True


def run_continuous(config: Config):
    """Run the monitor continuously at the configured interval."""
    db = ListingDatabase(config.db_path)

    logger.info(
        f"Woningmonitor gestart - controleer elke {config.check_interval_minutes} minuten\n"
        f"Zoeken in: {config.search.plaats} (+{config.search.straal_km}km)\n"
        f"Prijs: €{config.search.min_prijs:,} - €{config.search.max_prijs:,}\n"
        f"Bronnen: {len(ALL_SCRAPERS)} scrapers actief"
    )

    try:
        while True:
            logger.info("Nieuwe scan gestart...")
            stats = run_scan(config, db)
            logger.info(
                f"Scan voltooid: {stats['total_found']} gevonden, "
                f"{stats['new']} nieuw, {stats['updated']} gewijzigd, "
                f"{stats['errors']} fouten"
            )

            db_stats = db.get_stats()
            logger.info(f"Database: {db_stats['total']} woningen totaal, per bron: {db_stats['per_bron']}")

            logger.info(f"Volgende scan over {config.check_interval_minutes} minuten...")
            time.sleep(config.check_interval_minutes * 60)

    except KeyboardInterrupt:
        logger.info("Monitor gestopt door gebruiker")
    finally:
        db.close()
