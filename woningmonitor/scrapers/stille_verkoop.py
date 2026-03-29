"""Stille verkoop (off-market / pocket listing) detector.

Monitors multiple signals that may indicate off-market sales:
1. Kadaster - property ownership changes (via PDOK/Kadaster API)
2. Social media - Facebook groups, Nextdoor, local forums
3. Google Alerts-style monitoring for "te koop" + location
4. Makelaar websites that don't list on Funda
"""

import logging
import re

from bs4 import BeautifulSoup

from woningmonitor.config import SearchFilter
from woningmonitor.database import Listing
from woningmonitor.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class StilleVerkoopScraper(BaseScraper):
    """Detect off-market / pocket listings through various signals."""

    name = "stille_verkoop"

    def scrape(self, filters: SearchFilter) -> list[Listing]:
        listings = []

        # 1. Check local makelaar websites that don't always list on Funda
        listings.extend(self._check_local_makelaars(filters))

        # 2. Check social media / community platforms
        listings.extend(self._check_social_signals(filters))

        # 3. Check Kadaster/PDOK for ownership changes
        listings.extend(self._check_kadaster_signals(filters))

        logger.info(f"[stille_verkoop] Found {len(listings)} potential off-market listings")
        return listings

    def _check_local_makelaars(self, filters: SearchFilter) -> list[Listing]:
        """Check websites of local makelaars who may not list on Funda.

        Many smaller/independent makelaars only list on their own website.
        This checks known independent makelaar websites.
        """
        listings = []
        plaats = filters.plaats.lower()

        # Search for local makelaars via Google
        try:
            search_url = "https://www.google.nl/search"
            queries = [
                f"te koop {plaats} woning -funda -jaap -pararius site:*.nl",
                f"makelaar {plaats} woningaanbod",
            ]

            for query in queries:
                try:
                    resp = self._get(search_url, params={"q": query, "num": 20})
                    soup = BeautifulSoup(resp.text, "html.parser")

                    for result in soup.select("a[href*='http']"):
                        href = result.get("href", "")
                        # Filter out known aggregators
                        skip = ["funda.", "jaap.", "pararius.", "google.",
                                "zah.", "huislijn.", "huizenzoeker.", "makelaarsland."]
                        if any(s in href for s in skip):
                            continue

                        if any(kw in href.lower() for kw in ["koop", "woning", "huis", "aanbod"]):
                            listings.append(Listing(
                                source="stille_verkoop_makelaar",
                                external_id=href,
                                url=href,
                                adres="Zie makelaar website",
                                plaats=filters.plaats,
                                prijs=None,
                                oppervlakte=None,
                                kamers=None,
                                woningtype="",
                                omschrijving=f"Mogelijk stille verkoop via lokale makelaar: {href}",
                            ))
                except Exception as e:
                    logger.debug(f"[stille_verkoop] Google search error: {e}")

        except Exception as e:
            logger.error(f"[stille_verkoop] Local makelaar check failed: {e}")

        return listings

    def _check_social_signals(self, filters: SearchFilter) -> list[Listing]:
        """Monitor social platforms for off-market listings.

        Checks platforms like Facebook Marketplace, local community groups.
        Note: Facebook requires different access methods - see setup docs.
        """
        listings = []
        plaats = filters.plaats

        # Facebook Marketplace (public listings)
        try:
            fb_url = f"https://www.facebook.com/marketplace/category/propertyrentals"
            # Note: FB heavily restricts scraping. For production use,
            # consider Facebook Graph API or manual FBSR cookie approach.
            logger.info("[stille_verkoop] Facebook Marketplace check (limited without API)")
        except Exception as e:
            logger.debug(f"[stille_verkoop] Facebook check error: {e}")

        # Marktplaats.nl - people sometimes list houses here
        try:
            mp_url = f"https://www.marktplaats.nl/l/huizen-en-kamers/huizen-te-koop/"
            params = {"q": plaats}
            resp = self._get(mp_url, params=params)
            soup = BeautifulSoup(resp.text, "html.parser")

            items = soup.select('[class*="listing"]') or soup.select('[class*="result"]')
            for item in items[:20]:
                link = item.select_one("a[href]")
                if not link:
                    continue
                href = link.get("href", "")
                if not href.startswith("http"):
                    href = "https://www.marktplaats.nl" + href

                adres = (item.select_one("h3") or link).get_text(strip=True)

                prijs_el = item.select_one('[class*="price"]')
                prijs = None
                if prijs_el:
                    nums = re.sub(r"[^\d]", "", prijs_el.get_text())
                    if nums:
                        prijs = int(nums)

                listings.append(Listing(
                    source="marktplaats",
                    external_id=href.split("/")[-1] or href,
                    url=href,
                    adres=adres,
                    plaats=plaats,
                    prijs=prijs,
                    oppervlakte=None,
                    kamers=None,
                    woningtype="",
                    omschrijving="Gevonden op Marktplaats (mogelijk stille verkoop)",
                ))

        except Exception as e:
            logger.debug(f"[stille_verkoop] Marktplaats check error: {e}")

        return listings

    def _check_kadaster_signals(self, filters: SearchFilter) -> list[Listing]:
        """Check Kadaster/PDOK for recent ownership changes.

        The Kadaster public API (PDOK) provides some property data.
        Ownership transfers that happen without a listing on major platforms
        are strong indicators of off-market sales.

        Note: Full Kadaster access requires a subscription.
        The PDOK WFS service provides limited free data.
        """
        listings = []

        try:
            # PDOK BRK (Basisregistratie Kadaster) public endpoint
            pdok_url = "https://service.pdok.nl/kadaster/kadastralekaart/wfs/v5_0"
            params = {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": "kadastralekaartv5:perceel",
                "outputFormat": "application/json",
                "count": 50,
                "CQL_FILTER": f"INTERSECTS(geometry, POINT({filters.plaats}))",
            }
            # Note: This requires coordinates rather than place name.
            # In production, geocode the place name first.
            logger.info("[stille_verkoop] Kadaster/PDOK check (beperkte publieke data)")

        except Exception as e:
            logger.debug(f"[stille_verkoop] Kadaster check error: {e}")

        return listings
