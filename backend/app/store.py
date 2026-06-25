"""Buy / Rent store layer — additive feature on top of the search core.

The frozen `/search` contract returns catalog cars (MSRP + specs) from
Elasticsearch. This module turns a catalog car into a *purchasable/rentable
listing* by deriving, deterministically from its fields:

  * buy_price   -- purchase price (MSRP)
  * rent_daily  -- daily rental rate derived from MSRP
  * seats       -- estimated from body style
  * for_rent    -- whether the unit is offered for rent (~60% of catalog)
  * stock       -- units available for purchase (1-8), decremented by orders

Orders (purchases and rentals) are persisted in a small SQLite ledger. Stock
remaining for a car = derived stock − confirmed purchases for that car id, so no
mutable per-car state is needed beyond the orders table.

Nothing here touches the frozen search/recommend contract.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = Path(os.getenv("STORE_DB_PATH", ROOT / "data" / "store.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id  TEXT NOT NULL,
    label       TEXT NOT NULL,
    mode        TEXT NOT NULL,          -- 'buy' or 'rent'
    rent_days   INTEGER,
    total       REAL NOT NULL,
    customer    TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_orders_vehicle ON orders(vehicle_id);
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


# --------------------------------------------------------------------------- #
# Deterministic derivation (pure functions — unit-testable without ES)
# --------------------------------------------------------------------------- #
def _stable_hash(*parts: Any) -> int:
    digest = hashlib.md5("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(digest[:8], 16)


def estimate_seats(vehicle_style: str | None) -> int:
    """Estimate seating capacity from the body style string."""
    style = (vehicle_style or "").lower()
    if "passenger van" in style:
        return 12
    if "minivan" in style or "cargo van" in style:
        return 7
    if "suv" in style:
        return 7 if "4dr" in style else 5
    if "pickup" in style:
        return 5 if "crew" in style else 3
    if "convertible" in style or "coupe" in style or "roadster" in style:
        return 4
    if "sedan" in style or "hatchback" in style or "wagon" in style:
        return 5
    return 5


def derive_rent_daily(msrp: float | None, vehicle_style: str | None) -> float:
    """Daily rental rate derived from MSRP (≈ a $30k car -> ~$40/day)."""
    if not msrp:
        return 25.0
    base = msrp * 0.0008 + 18
    style = (vehicle_style or "").lower()
    if "suv" in style or "pickup" in style:
        base *= 1.1  # larger vehicles rent for a bit more
    return float(max(15, round(base / 5) * 5))


# Inverse of derive_rent_daily (ignoring the body-style multiplier) so a daily
# rent range can be pushed down to ES as an approximate MSRP range, keeping the
# search core's pagination/totals authoritative.
def rent_daily_to_msrp(rent_daily: float) -> float:
    return max(0.0, (rent_daily - 18) / 0.0008)


def offered_for_rent(vehicle_id: str) -> bool:
    """Deterministically offer ~60% of the catalog for rent."""
    return _stable_hash("rent", vehicle_id) % 10 < 6


def base_stock(vehicle_id: str) -> int:
    """Deterministic purchase stock between 1 and 8 (before orders)."""
    return 1 + _stable_hash("stock", vehicle_id) % 8


# --------------------------------------------------------------------------- #
# Listing assembly
# --------------------------------------------------------------------------- #
def purchases_by_vehicle() -> dict[str, int]:
    """Confirmed purchase counts per vehicle id (to compute remaining stock)."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT vehicle_id, COUNT(*) AS n FROM orders WHERE mode='buy' GROUP BY vehicle_id"
        ).fetchall()
    finally:
        conn.close()
    return {r["vehicle_id"]: r["n"] for r in rows}


def to_listing(car: dict[str, Any], *, verified: bool, sold: int = 0) -> dict[str, Any]:
    """Augment a catalog car dict (from search_service) into a store listing."""
    vid = str(car.get("id"))
    style = car.get("vehicle_style")
    stock = max(0, base_stock(vid) - sold)
    return {
        **car,
        "buy_price": float(car.get("msrp") or 0),
        "rent_daily": derive_rent_daily(car.get("msrp"), style),
        "seats": estimate_seats(style),
        "for_rent": offered_for_rent(vid),
        "stock": stock,
        "vpic_verified": verified,
    }


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #
def record_order(
    vehicle_id: str, label: str, mode: str, total: float,
    rent_days: int | None = None, customer: str | None = None,
) -> int:
    conn = _conn()
    try:
        cur = conn.execute(
            """INSERT INTO orders (vehicle_id, label, mode, rent_days, total, customer)
               VALUES (?,?,?,?,?,?)""",
            [vehicle_id, label, mode, rent_days, total, customer],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_orders(limit: int = 100) -> list[dict[str, Any]]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT ?", [limit]
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
