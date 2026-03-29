"""Jaap.nl scraper - Dutch real estate aggregator."""

import logging
import re

from bs4 import BeautifulSoup

from woningmonitor.config import SearchFilter
from woningmonitor.database import Listing
from woningmonitor.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class JaapScraper(BaseScraper):
    name = "jaap"
    base_url = "https://www.jaap.nl"

    def scrape(self, filters: SearchFilter) -> list[Listing]:
        listings = []
        plaats = filters.plaats.lower().replace(" ", "+")

        url = f"{self.base_url}/koophuizen/{filters.plaats.lower()}"
        params = {}
        if filters.max_prijs < 10_000_000:
            params["max"] = filters.max_prijs
        if filters.min_prijs > 0:
            params["min"] = filters.min_prijs
        if filters.straal_km > 0:
            params["straal"] = filters.straal_km

        page = 1
        while page <= 10:
            page_params = {**params}
            if page > 1:
                page_params["p"] = page

            try:
                resp = self._get(url, params=page_params)
                soup = BeautifulSoup(resp.text, "html.parser")

                items = soup.select(".property-list .property") or soup.select('[class*="property"]')
                if not items:
                    break

                for item in items:
                    listing = self._parse_item(item)
                    if listing:
                        listings.append(listing)

                next_link = soup.select_one('a[rel="next"]') or soup.select_one(".next")
                if not next_link:
                    break
                page += 1

            except Exception as e:
                logger.error(f"[jaap] Error scraping page {page}: {e}")
                break

        logger.info(f"[jaap] Found {len(listings)} listings")
        return listings

    def _parse_item(self, item) -> Listing | None:
        try:
            link = item.select_one("a[href]")
            if not link:
                return None

            href = link.get("href", "")
            if not href.startswith("http"):
                href = self.base_url + href

            adres_el = item.select_one("h2") or item.select_one('[class*="address"]') or link
            adres = adres_el.get_text(strip=True)

            prijs_el = item.select_one('[class*="price"]') or item.select_one('[class*="prijs"]')
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

            plaats_el = item.select_one('[class*="place"]') or item.select_one('[class*="stad"]')
            plaats = plaats_el.get_text(strip=True) if plaats_el else ""

            external_id = href.rstrip("/").split("/")[-1] or href

            return Listing(
                source="jaap",
                external_id=external_id,
                url=href,
                adres=adres,
                plaats=plaats,
                prijs=prijs,
                oppervlakte=oppervlakte,
                kamers=kamers,
                woningtype="",
            )
        except Exception as e:
            logger.debug(f"[jaap] Parse error: {e}")
            return None

    @staticmethod
    def _parse_prijs(text: str) -> int | None:
        if not text or "aanvraag" in text.lower():
            return None
        cleaned = re.sub(r"[^\d]", "", text)
        return int(cleaned) if cleaned else None
