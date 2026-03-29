"""Makelaarsland.nl scraper - online makelaar with own listings."""

import logging
import re

from bs4 import BeautifulSoup

from woningmonitor.config import SearchFilter
from woningmonitor.database import Listing
from woningmonitor.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class MakelaarslandScraper(BaseScraper):
    name = "makelaarsland"
    base_url = "https://www.makelaarsland.nl"

    def scrape(self, filters: SearchFilter) -> list[Listing]:
        listings = []
        plaats = filters.plaats.lower().replace(" ", "-")

        url = f"{self.base_url}/woningaanbod/{plaats}"
        params = {}
        if filters.max_prijs < 10_000_000:
            params["maxPrice"] = filters.max_prijs
        if filters.min_prijs > 0:
            params["minPrice"] = filters.min_prijs

        try:
            resp = self._get(url, params=params)
            soup = BeautifulSoup(resp.text, "html.parser")

            items = soup.select('[class*="property"]') or soup.select('[class*="woning"]')
            for item in items:
                listing = self._parse_item(item)
                if listing:
                    listings.append(listing)

        except Exception as e:
            logger.error(f"[makelaarsland] Error scraping: {e}")

        logger.info(f"[makelaarsland] Found {len(listings)} listings")
        return listings

    def _parse_item(self, item) -> Listing | None:
        try:
            link = item.select_one("a[href]")
            if not link:
                return None

            href = link.get("href", "")
            if not href.startswith("http"):
                href = self.base_url + href

            adres = (item.select_one("h2") or item.select_one("h3") or link).get_text(strip=True)

            prijs_el = item.select_one('[class*="price"]') or item.select_one('[class*="prijs"]')
            prijs = None
            if prijs_el:
                nums = re.sub(r"[^\d]", "", prijs_el.get_text(strip=True))
                if nums:
                    prijs = int(nums)

            text = item.get_text()
            oppervlakte = None
            kamers = None
            m2 = re.search(r"(\d+)\s*m²", text)
            if m2:
                oppervlakte = int(m2.group(1))
            km = re.search(r"(\d+)\s*kamer", text)
            if km:
                kamers = int(km.group(1))

            external_id = href.rstrip("/").split("/")[-1] or href

            return Listing(
                source="makelaarsland",
                external_id=external_id,
                url=href,
                adres=adres,
                plaats="",
                prijs=prijs,
                oppervlakte=oppervlakte,
                kamers=kamers,
                woningtype="",
                makelaar="Makelaarsland",
            )
        except Exception as e:
            logger.debug(f"[makelaarsland] Parse error: {e}")
            return None
