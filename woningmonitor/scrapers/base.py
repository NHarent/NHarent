"""Base scraper class."""

import logging
import time
from abc import ABC, abstractmethod

import requests

from woningmonitor.config import SearchFilter
from woningmonitor.database import Listing

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for all property scrapers."""

    name: str = "base"
    base_url: str = ""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

    @abstractmethod
    def scrape(self, filters: SearchFilter) -> list[Listing]:
        """Scrape listings from this source."""
        ...

    def _get(self, url: str, params: dict | None = None, **kwargs) -> requests.Response:
        """Make a GET request with rate limiting and error handling."""
        try:
            time.sleep(1)  # polite delay
            resp = self.session.get(url, params=params, timeout=30, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            logger.warning(f"[{self.name}] Request failed for {url}: {e}")
            raise
