"""Huislijn.nl scraper - Dutch real estate aggregator with many small agencies."""

import logging
import re

from bs4 import BeautifulSoup

from woningmonitor.config import SearchFilter
from woningmonitor.database import Listing
from woningmonitor.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class HuislijnScraper(BaseScraper):
    name = "huislijn"
    base_url = "https://www.huislijn.nl"

    def scrape(self, filters: SearchFilter) -> list[Listing]:
        listings = []
        plaats = filters.plaats.lower()

        url = f"{self.base_url}/koopwoning/{plaats}"
        params = {}
        if filters.max_prijs < 10_000_000:
            params["prijstot"] = filters.max_prijs
        if filters.min_prijs > 0:
            params["prijsvan"] = filters.min_prijs

        try:
            resp = self._get(url, params=params)
            soup = BeautifulSoup(resp.text, "html.parser")

            items = soup.select(".object-list .object") or soup.select('[class*="woningaanbod"]')
            for item in items:
                listing = self._parse_item(item)
                if listing:
                    listings.append(listing)

        except Exception as e:
            logger.error(f"[huislijn] Error scraping: {e}")

        logger.info(f"[huislijn] Found {len(listings)} listings")
        return listings

    def _parse_item(self, item) -> Listing | None:
        try:
            link = item.select_one("a[href]")
            if not link:
                return None

            href = link.get("href", "")
            if not href.startswith("http"):
                href = self.base_url + href

            adres = (item.select_one('[class*="address"]') or link).get_text(strip=True)

            prijs_el = item.select_one('[class*="price"]') or item.select_one('[class*="prijs"]')
            prijs_text = prijs_el.get_text(strip=True) if prijs_el else ""
            prijs = None
            nums = re.sub(r"[^\d]", "", prijs_text)
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
                source="huislijn",
                external_id=external_id,
                url=href,
                adres=adres,
                plaats="",
                prijs=prijs,
                oppervlakte=oppervlakte,
                kamers=kamers,
                woningtype="",
            )
        except Exception as e:
            logger.debug(f"[huislijn] Parse error: {e}")
            return None
