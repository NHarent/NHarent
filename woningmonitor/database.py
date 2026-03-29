"""SQLite database for tracking listings and detecting new ones."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Listing:
    """A single property listing."""
    source: str  # e.g. "funda", "jaap", "pararius"
    external_id: str  # unique ID from the source
    url: str
    adres: str
    plaats: str
    prijs: int | None  # in euros, None = prijs op aanvraag
    oppervlakte: int | None  # m²
    kamers: int | None
    woningtype: str
    omschrijving: str = ""
    foto_url: str = ""
    makelaar: str = ""
    status: str = "te koop"  # te koop, verkocht, onder bod
    eerst_gezien: str = ""
    laatst_gezien: str = ""


class ListingDatabase:
    def __init__(self, db_path: str = "woningmonitor.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                external_id TEXT NOT NULL,
                url TEXT NOT NULL,
                adres TEXT NOT NULL,
                plaats TEXT NOT NULL,
                prijs INTEGER,
                oppervlakte INTEGER,
                kamers INTEGER,
                woningtype TEXT,
                omschrijving TEXT DEFAULT '',
                foto_url TEXT DEFAULT '',
                makelaar TEXT DEFAULT '',
                status TEXT DEFAULT 'te koop',
                eerst_gezien TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                laatst_gezien TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notified INTEGER DEFAULT 0,
                UNIQUE(source, external_id)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS price_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER NOT NULL,
                oude_prijs INTEGER,
                nieuwe_prijs INTEGER,
                datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (listing_id) REFERENCES listings(id)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS status_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER NOT NULL,
                oude_status TEXT,
                nieuwe_status TEXT,
                datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (listing_id) REFERENCES listings(id)
            )
        """)
        self.conn.commit()

    def upsert_listing(self, listing: Listing) -> tuple[bool, bool, Listing | None]:
        """Insert or update a listing. Returns (is_new, has_changes, old_listing)."""
        cursor = self.conn.execute(
            "SELECT * FROM listings WHERE source = ? AND external_id = ?",
            (listing.source, listing.external_id),
        )
        existing = cursor.fetchone()

        if existing is None:
            self.conn.execute(
                """INSERT INTO listings
                   (source, external_id, url, adres, plaats, prijs, oppervlakte,
                    kamers, woningtype, omschrijving, foto_url, makelaar, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (listing.source, listing.external_id, listing.url, listing.adres,
                 listing.plaats, listing.prijs, listing.oppervlakte, listing.kamers,
                 listing.woningtype, listing.omschrijving, listing.foto_url,
                 listing.makelaar, listing.status),
            )
            self.conn.commit()
            return True, False, None

        old = Listing(
            source=existing["source"], external_id=existing["external_id"],
            url=existing["url"], adres=existing["adres"], plaats=existing["plaats"],
            prijs=existing["prijs"], oppervlakte=existing["oppervlakte"],
            kamers=existing["kamers"], woningtype=existing["woningtype"],
            omschrijving=existing["omschrijving"], foto_url=existing["foto_url"],
            makelaar=existing["makelaar"], status=existing["status"],
        )

        has_changes = False

        if listing.prijs != existing["prijs"]:
            has_changes = True
            self.conn.execute(
                "INSERT INTO price_changes (listing_id, oude_prijs, nieuwe_prijs) VALUES (?, ?, ?)",
                (existing["id"], existing["prijs"], listing.prijs),
            )

        if listing.status != existing["status"]:
            has_changes = True
            self.conn.execute(
                "INSERT INTO status_changes (listing_id, oude_status, nieuwe_status) VALUES (?, ?, ?)",
                (existing["id"], existing["status"], listing.status),
            )

        self.conn.execute(
            """UPDATE listings SET prijs=?, oppervlakte=?, kamers=?, status=?,
               omschrijving=?, foto_url=?, laatst_gezien=CURRENT_TIMESTAMP
               WHERE source=? AND external_id=?""",
            (listing.prijs, listing.oppervlakte, listing.kamers, listing.status,
             listing.omschrijving, listing.foto_url, listing.source, listing.external_id),
        )
        self.conn.commit()
        return False, has_changes, old

    def mark_notified(self, source: str, external_id: str):
        self.conn.execute(
            "UPDATE listings SET notified=1 WHERE source=? AND external_id=?",
            (source, external_id),
        )
        self.conn.commit()

    def get_stats(self) -> dict:
        row = self.conn.execute("SELECT COUNT(*) as total FROM listings").fetchone()
        sources = self.conn.execute(
            "SELECT source, COUNT(*) as count FROM listings GROUP BY source"
        ).fetchall()
        return {
            "total": row["total"],
            "per_bron": {r["source"]: r["count"] for r in sources},
        }

    def close(self):
        self.conn.close()
