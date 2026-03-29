"""Zah.nl (Zoek alle huizen) scraper - meta-search aggregator."""

import logging
import re

from bs4 import BeautifulSoup

from woningmonitor.config import SearchFilter
from woningmonitor.database import Listing
from woningmonitor.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class ZahScraper(BaseScraper):
    name = "zah"
    base_url = "https://www.zah.nl"

    def scrape(self, filters: SearchFilter) -> list[Listing]:
        listings = []
        plaats = filters.plaats.lower().replace(" ", "-")

        url = f"{self.base_url}/koop/{plaats}"
        params = {"radius": filters.straal_km}
        if filters.max_prijs < 10_000_000:
            params["maxprice"] = filters.max_prijs
        if filters.min_prijs > 0:
            params["minprice"] = filters.min_prijs

        page = 1
        while page <= 5:
            page_params = {**params}
            if page > 1:
                page_params["page"] = page

            try:
                resp = self._get(url, params=page_params)
                soup = BeautifulSoup(resp.text, "html.parser")

                items = soup.select(".property") or soup.select('[class*="result"]')
                if not items:
                    break

                for item in items:
                    listing = self._parse_item(item)
                    if listing:
                        listings.append(listing)

                next_link = soup.select_one('[rel="next"]') or soup.select_one(".next")
                if not next_link:
                    break
                page += 1

            except Exception as e:
                logger.error(f"[zah] Error scraping page {page}: {e}")
                break

        logger.info(f"[zah] Found {len(listings)} listings")
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

            prijs_el = item.select_one('[class*="price"]')
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

            makelaar_el = item.select_one('[class*="agent"]') or item.select_one('[class*="makelaar"]')
            makelaar = makelaar_el.get_text(strip=True) if makelaar_el else ""

            external_id = href.rstrip("/").split("/")[-1] or href

            return Listing(
                source="zah",
                external_id=external_id,
                url=href,
                adres=adres,
                plaats="",
                prijs=prijs,
                oppervlakte=oppervlakte,
                kamers=kamers,
                woningtype="",
                makelaar=makelaar,
            )
        except Exception as e:
            logger.debug(f"[zah] Parse error: {e}")
            return None
