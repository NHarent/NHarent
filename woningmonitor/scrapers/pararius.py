"""Pararius.nl scraper - Dutch real estate platform (koop & huur)."""

import logging
import re

from bs4 import BeautifulSoup

from woningmonitor.config import SearchFilter
from woningmonitor.database import Listing
from woningmonitor.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class ParariusScraper(BaseScraper):
    name = "pararius"
    base_url = "https://www.pararius.nl"

    def scrape(self, filters: SearchFilter) -> list[Listing]:
        listings = []
        plaats = filters.plaats.lower().replace(" ", "-")

        url = f"{self.base_url}/koopwoningen/{plaats}"
        params = {}
        if filters.min_prijs > 0:
            params["ac"] = filters.min_prijs
        if filters.max_prijs < 10_000_000:
            params["ae"] = filters.max_prijs
        if filters.min_oppervlakte > 0:
            params["ah"] = filters.min_oppervlakte

        page = 1
        while page <= 10:
            page_url = url if page == 1 else f"{url}/page-{page}"

            try:
                resp = self._get(page_url, params=params)
                soup = BeautifulSoup(resp.text, "html.parser")

                items = soup.select(".search-list__item--listing") or soup.select('[class*="listing-search-item"]')
                if not items:
                    break

                for item in items:
                    listing = self._parse_item(item)
                    if listing:
                        listings.append(listing)

                next_link = soup.select_one('[rel="next"]')
                if not next_link:
                    break
                page += 1

            except Exception as e:
                logger.error(f"[pararius] Error scraping page {page}: {e}")
                break

        logger.info(f"[pararius] Found {len(listings)} listings")
        return listings

    def _parse_item(self, item) -> Listing | None:
        try:
            link = item.select_one("a[href*='/koopwoning']") or item.select_one("a[href]")
            if not link:
                return None

            href = link.get("href", "")
            if not href.startswith("http"):
                href = self.base_url + href

            adres_el = item.select_one('[class*="title"]') or item.select_one("h2") or link
            adres = adres_el.get_text(strip=True)

            prijs_el = item.select_one('[class*="price"]')
            prijs = self._parse_prijs(prijs_el.get_text(strip=True) if prijs_el else "")

            details_text = item.get_text()
            oppervlakte = None
            kamers = None
            m2 = re.search(r"(\d+)\s*m²", details_text)
            if m2:
                oppervlakte = int(m2.group(1))
            km = re.search(r"(\d+)\s*kamer", details_text)
            if km:
                kamers = int(km.group(1))

            external_id = href.rstrip("/").split("/")[-1] or href

            return Listing(
                source="pararius",
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
            logger.debug(f"[pararius] Parse error: {e}")
            return None

    @staticmethod
    def _parse_prijs(text: str) -> int | None:
        if not text or "aanvraag" in text.lower():
            return None
        cleaned = re.sub(r"[^\d]", "", text)
        return int(cleaned) if cleaned else None
