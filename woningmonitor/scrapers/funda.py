"""Funda.nl scraper - largest Dutch real estate platform."""

import logging
import re

from bs4 import BeautifulSoup

from woningmonitor.config import SearchFilter
from woningmonitor.database import Listing
from woningmonitor.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class FundaScraper(BaseScraper):
    name = "funda"
    base_url = "https://www.funda.nl"

    def scrape(self, filters: SearchFilter) -> list[Listing]:
        listings = []
        plaats = filters.plaats.lower().replace(" ", "-")

        # Build URL with filters
        url = f"{self.base_url}/zoeken/koop/{plaats}/{filters.straal_km}km/"
        params = {}
        if filters.min_prijs > 0:
            params["price"] = f'"{filters.min_prijs}-{filters.max_prijs}"'
        elif filters.max_prijs < 10_000_000:
            params["price"] = f'"-{filters.max_prijs}"'
        if filters.min_oppervlakte > 0:
            params["floor_area"] = f'"{filters.min_oppervlakte}-"'

        page = 1
        while page <= 10:  # max 10 pages
            page_params = {**params}
            if page > 1:
                page_params["search_result"] = page

            try:
                resp = self._get(url, params=page_params)
                soup = BeautifulSoup(resp.text, "html.parser")
                results = soup.select('[data-test-id="search-result-item"]')

                if not results:
                    # Try alternative selectors
                    results = soup.select(".search-result__header-title-col")
                    if not results:
                        break

                for item in results:
                    listing = self._parse_item(item, soup)
                    if listing:
                        listings.append(listing)

                # Check for next page
                next_btn = soup.select_one('[rel="next"]')
                if not next_btn:
                    break
                page += 1

            except Exception as e:
                logger.error(f"[funda] Error scraping page {page}: {e}")
                break

        logger.info(f"[funda] Found {len(listings)} listings")
        return listings

    def _parse_item(self, item, soup) -> Listing | None:
        try:
            # Extract link and address
            link = item.select_one("a[href*='/koop/']")
            if not link:
                link = item.find("a")
            if not link:
                return None

            href = link.get("href", "")
            if not href.startswith("http"):
                href = self.base_url + href

            adres_el = item.select_one("h2") or link
            adres = adres_el.get_text(strip=True) if adres_el else ""

            # Extract price
            prijs_el = item.select_one('[class*="price"]') or item.select_one(".search-result-price")
            prijs_text = prijs_el.get_text(strip=True) if prijs_el else ""
            prijs = self._parse_prijs(prijs_text)

            # Extract details
            details = item.select('[class*="kenmerken"]') or item.select("li")
            oppervlakte = None
            kamers = None
            for d in details:
                text = d.get_text(strip=True)
                m2_match = re.search(r"(\d+)\s*m²", text)
                if m2_match:
                    oppervlakte = int(m2_match.group(1))
                kamers_match = re.search(r"(\d+)\s*kamer", text)
                if kamers_match:
                    kamers = int(kamers_match.group(1))

            # Extract external ID from URL
            external_id = href.rstrip("/").split("/")[-1] or href

            # Extract plaats from URL or address
            plaats = ""
            url_parts = href.split("/koop/")
            if len(url_parts) > 1:
                plaats = url_parts[1].split("/")[0].replace("-", " ").title()

            return Listing(
                source="funda",
                external_id=external_id,
                url=href,
                adres=adres,
                plaats=plaats,
                prijs=prijs,
                oppervlakte=oppervlakte,
                kamers=kamers,
                woningtype="",
                makelaar="",
            )
        except Exception as e:
            logger.debug(f"[funda] Parse error: {e}")
            return None

    @staticmethod
    def _parse_prijs(text: str) -> int | None:
        if not text or "aanvraag" in text.lower():
            return None
        numbers = re.findall(r"[\d.]+", text.replace(".", ""))
        if numbers:
            try:
                return int(numbers[0])
            except ValueError:
                return None
        return None
