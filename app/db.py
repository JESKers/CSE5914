"""SQLite catalog for the car store.

The catalog is seeded from data/data.csv (real make/model/spec/MSRP rows) and
enriched with:

  * vpic_make_id   -- joined against the vPIC make directory so every brand is
                      verifiable against NHTSA's authoritative list.
  * buy_price      -- purchase price (MSRP).
  * rent_daily     -- derived daily rental rate.
  * seats          -- estimated from body style / door count.
  * for_rent       -- whether the unit is offered for rent.
  * stock          -- units available for purchase.

Seeding is idempotent: the DB is (re)built from the CSV only when empty.
"""
from __future__ import annotations

import csv
import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from . import vpic

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("CARS_DB_PATH", ROOT / "data" / "cars.db"))
CSV_PATH = Path(os.getenv("CARS_CSV_PATH", ROOT / "data" / "data.csv"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS vehicles (
    id              INTEGER PRIMARY KEY,
    make            TEXT NOT NULL,
    model           TEXT NOT NULL,
    year            INTEGER NOT NULL,
    fuel_type       TEXT,
    engine_hp       INTEGER,
    cylinders       INTEGER,
    transmission    TEXT,
    drive           TEXT,
    doors           INTEGER,
    market_category TEXT,
    size            TEXT,
    body_style      TEXT,
    mpg_hwy         INTEGER,
    mpg_city        INTEGER,
    popularity      INTEGER,
    msrp            INTEGER NOT NULL,
    buy_price       INTEGER NOT NULL,
    rent_daily      INTEGER NOT NULL,
    seats           INTEGER,
    for_sale        INTEGER NOT NULL DEFAULT 1,
    for_rent        INTEGER NOT NULL DEFAULT 0,
    stock           INTEGER NOT NULL DEFAULT 0,
    vpic_make_id    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_make   ON vehicles(make);
CREATE INDEX IF NOT EXISTS idx_price  ON vehicles(buy_price);
CREATE INDEX IF NOT EXISTS idx_style  ON vehicles(body_style);
CREATE INDEX IF NOT EXISTS idx_year   ON vehicles(year);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id  INTEGER NOT NULL,
    mode        TEXT NOT NULL,          -- 'buy' or 'rent'
    rent_days   INTEGER,
    total       INTEGER NOT NULL,
    customer    TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --------------------------------------------------------------------------- #
# Derivation helpers
# --------------------------------------------------------------------------- #
def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def estimate_seats(body_style: str, doors: int) -> int:
    """Estimate seating capacity from body style and door count."""
    style = (body_style or "").lower()
    if "passenger" in style or "minivan" in style:
        return 7 if "minivan" in style else 12
    if "suv" in style:
        return 7 if "4dr" in style else 5
    if "pickup" in style:
        return 5 if "crew" in style else 3
    if "convertible" in style or "coupe" in style or "roadster" in style:
        return 4 if doors >= 2 else 2
    if "sedan" in style or "hatchback" in style or "wagon" in style:
        return 5
    return 5 if doors >= 4 else 4


def derive_rent_daily(msrp: int, body_style: str) -> int:
    """Daily rental rate derived from MSRP (≈ a $30k car -> ~$40/day)."""
    base = msrp * 0.0008 + 18
    if "suv" in (body_style or "").lower() or "pickup" in (body_style or "").lower():
        base *= 1.1  # bigger vehicles rent for a bit more
    return max(15, round(base / 5) * 5)


def _stable_hash(*parts: Any) -> int:
    digest = hashlib.md5("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(digest[:8], 16)


def _offered_for_rent(make: str, model: str, year: int) -> bool:
    """Deterministically offer ~60% of the catalog for rent."""
    return _stable_hash(make, model, year) % 10 < 6


def _stock_for(make: str, model: str, year: int) -> int:
    """Deterministic purchase stock between 1 and 8."""
    return 1 + _stable_hash("stock", make, model, year) % 8


# --------------------------------------------------------------------------- #
# Seeding
# --------------------------------------------------------------------------- #
def _csv_rows(make_index: dict[str, int]) -> Iterable[tuple]:
    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            make = row["Make"].strip()
            model = row["Model"].strip()
            year = _int(row["Year"])
            body_style = row["Vehicle Style"].strip()
            doors = _int(row["Number of Doors"], 4)
            msrp = _int(row["MSRP"])
            if msrp <= 0:
                continue
            yield (
                make,
                model,
                year,
                row["Engine Fuel Type"].strip(),
                _int(row["Engine HP"]),
                _int(row["Engine Cylinders"]),
                row["Transmission Type"].strip(),
                row["Driven_Wheels"].strip(),
                doors,
                row["Market Category"].strip(),
                row["Vehicle Size"].strip(),
                body_style,
                _int(row["highway MPG"]),
                _int(row["city mpg"]),
                _int(row["Popularity"]),
                msrp,
                msrp,                                       # buy_price
                derive_rent_daily(msrp, body_style),        # rent_daily
                estimate_seats(body_style, doors),          # seats
                1,                                          # for_sale
                1 if _offered_for_rent(make, model, year) else 0,
                _stock_for(make, model, year),              # stock
                make_index.get(make.upper()),               # vpic_make_id
            )


def seed(force: bool = False) -> int:
    """Build the catalog from CSV if empty (or force=True). Returns row count."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        if force:
            conn.execute("DELETE FROM vehicles")
        count = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
        if count and not force:
            return count

        # Pull the vPIC make directory once so each brand can be verified.
        make_index = vpic.make_id_index()

        conn.executemany(
            """INSERT INTO vehicles (
                make, model, year, fuel_type, engine_hp, cylinders, transmission,
                drive, doors, market_category, size, body_style, mpg_hwy, mpg_city,
                popularity, msrp, buy_price, rent_daily, seats, for_sale, for_rent,
                stock, vpic_make_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            _csv_rows(make_index),
        )
        conn.commit()
        return conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
    finally:
        conn.close()


if __name__ == "__main__":
    n = seed(force=True)
    print(f"Seeded {n} vehicles into {DB_PATH}")
