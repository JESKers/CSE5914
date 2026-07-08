"""Synthetic finance / TCO + rental / dealer layer — additive demo feature.

The car catalog (`/search`) only carries specs + MSRP. To power a buying advisor
(loan vs lease vs CPO total-cost-of-ownership) and a fully-automated rental agent
(inventory -> add-ons -> insurance -> booking), the real world needs data the
Kaggle/vPIC snapshots don't have: interest rates, residual values, depreciation,
maintenance, insurance, rental fleets, add-on catalogs, dealer contacts.

All of that is *synthetic* and lives in `data/synth/*.json`. This module loads
those tables and applies them deterministically to a catalog car, mirroring the
pure-function style of `store.py`. Nothing here touches the frozen search contract.

Bookings (rentals) and test-drive appointments are persisted alongside orders in
the same SQLite ledger via extra tables created here.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
SYNTH_DIR = ROOT / "data" / "synth"
from .store import DB_PATH, _conn as _store_conn  # reuse the same SQLite ledger


# --------------------------------------------------------------------------- #
# Reference-table loading
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=None)
def _table(name: str) -> dict[str, Any]:
    with open(SYNTH_DIR / f"{name}.json", encoding="utf-8") as fh:
        return json.load(fh)


def _stable_hash(*parts: Any) -> int:
    digest = hashlib.md5("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(digest[:8], 16)


# --------------------------------------------------------------------------- #
# Classification helpers (map a catalog car to a segment / brand tier)
# --------------------------------------------------------------------------- #
def segment_of(car: dict[str, Any]) -> str:
    """Bucket a car into a pricing segment used by lease/depreciation/insurance."""
    style = (car.get("vehicle_style") or "").lower()
    size = (car.get("vehicle_size") or "").lower()
    market = (car.get("market_category") or "").lower()
    msrp = float(car.get("msrp") or 0)
    if "performance" in market or "high-performance" in market:
        return "performance"
    if "luxury" in market or msrp >= 55000:
        return "luxury"
    if "pickup" in style:
        return "truck"
    if "suv" in style or "crossover" in style:
        return "suv"
    if "large" in size:
        return "midsize"
    if "compact" in size or "hatchback" in style:
        return "economy"
    return "midsize"


def brand_tier(make: str | None) -> str:
    tiers = _table("ownership_costs")["maintenance_annual"]["brand_tier"]
    m = (make or "").strip()
    for tier, spec in tiers.items():
        if m in spec["brands"]:
            return tier
    return "medium"


def credit_tier_from_score(score: int | None) -> str:
    tiers = _table("finance_rates")["credit_tiers"]
    ranked = sorted(tiers.items(), key=lambda kv: kv[1]["min_score"], reverse=True)
    for name, spec in ranked:
        if score is not None and score >= spec["min_score"]:
            return name
    return "deep"


# --------------------------------------------------------------------------- #
# Finance: loan quote
# --------------------------------------------------------------------------- #
def loan_apr(*, credit: str, condition: str, term_months: int) -> float:
    fr = _table("finance_rates")
    apr = fr["apr_new"][credit]
    if condition == "cpo":
        apr += fr["apr_used_premium"]["cpo"]
    elif condition == "used":
        apr += fr["apr_used_premium"]["used"]
    apr += fr["term_premium"].get(str(term_months), 0.0)
    return round(apr, 2)


def _monthly_payment(principal: float, apr: float, term_months: int) -> float:
    r = apr / 100 / 12
    if r == 0:
        return principal / term_months
    return principal * r / (1 - (1 + r) ** -term_months)


def quote_loan(
    price: float, *, credit_score: int | None = None, condition: str = "new",
    term_months: int = 60, down_payment: float | None = None, state: str = "OH",
) -> dict[str, Any]:
    """Full financed-purchase quote: taxes, fees, monthly payment, total cost."""
    fr = _table("finance_rates")
    credit = credit_tier_from_score(credit_score)
    apr = loan_apr(credit=credit, condition=condition, term_months=term_months)
    tax_pct = fr["sales_tax_pct_by_state"].get(state, fr["sales_tax_pct_by_state"]["_default"])
    tax = price * tax_pct
    fees = fr["doc_and_registration_fee"]
    if down_payment is None:
        down_payment = price * fr["default_down_payment_pct"]
    financed = max(0.0, price + tax + fees - down_payment)
    monthly = _monthly_payment(financed, apr, term_months)
    total_paid = monthly * term_months + down_payment
    return {
        "credit_tier": credit, "apr": apr, "term_months": term_months,
        "price": round(price, 2), "sales_tax": round(tax, 2), "fees": fees,
        "down_payment": round(down_payment, 2), "amount_financed": round(financed, 2),
        "monthly_payment": round(monthly, 2), "total_of_payments": round(total_paid, 2),
        "total_interest": round(monthly * term_months - financed, 2),
    }


# --------------------------------------------------------------------------- #
# Finance: lease quote
# --------------------------------------------------------------------------- #
def quote_lease(
    car: dict[str, Any], *, credit_score: int | None = None,
    term_months: int = 36, annual_miles: int = 12000, down_payment: float = 0.0,
) -> dict[str, Any]:
    lp = _table("lease_params")
    msrp = float(car.get("msrp") or 0)
    seg = segment_of(car)
    credit = credit_tier_from_score(credit_score)
    residual_pct = lp["residual_pct"].get(seg, lp["residual_pct"]["midsize"]).get(
        str(term_months), lp["residual_pct"]["midsize"]["36"]
    )
    residual = msrp * residual_pct
    mf = lp["money_factor_by_credit"][credit]
    cap_cost = msrp - down_payment
    depreciation = (cap_cost - residual) / term_months
    rent_charge = (cap_cost + residual) * mf
    monthly = depreciation + rent_charge
    total = monthly * term_months + lp["acquisition_fee"] + lp["disposition_fee"] + down_payment
    return {
        "credit_tier": credit, "term_months": term_months, "annual_miles": annual_miles,
        "msrp": round(msrp, 2), "residual_pct": residual_pct, "residual_value": round(residual, 2),
        "money_factor": mf, "approx_apr": round(mf * 2400, 2),
        "monthly_payment": round(monthly, 2),
        "acquisition_fee": lp["acquisition_fee"], "disposition_fee": lp["disposition_fee"],
        "due_at_signing": round(down_payment + monthly + lp["acquisition_fee"], 2),
        "total_cost": round(total, 2),
    }


# --------------------------------------------------------------------------- #
# Ownership cost pieces (annual) + depreciation
# --------------------------------------------------------------------------- #
def annual_maintenance(car: dict[str, Any], age: int) -> float:
    oc = _table("ownership_costs")["maintenance_annual"]
    base = oc["brand_tier"].get(brand_tier(car.get("make")), {}).get("base", oc["default_base"])
    return round(base * (1 + oc["age_escalation_per_year"] * age), 2)


def annual_insurance(car: dict[str, Any], value: float) -> float:
    ins = _table("ownership_costs")["insurance_annual"]
    mult = ins["class_multiplier"].get(segment_of(car), 1.0)
    return round((ins["base"] + ins["value_factor"] * value) * mult, 2)


def annual_fuel(car: dict[str, Any], annual_miles: int = 12000) -> float:
    fuel = _table("ownership_costs")["fuel"]
    fuel_type = (car.get("engine_fuel_type") or "").lower()
    mpg = car.get("city_mpg") or car.get("highway_mpg") or 25
    if "electric" in fuel_type:
        kwh = annual_miles / 3.0  # ~3 mi/kWh
        return round(kwh * fuel["electricity_price_per_kwh"], 2)
    gallons = annual_miles / max(1, mpg)
    return round(gallons * fuel["gas_price_per_gallon"], 2)


def retained_value(car: dict[str, Any], price: float, years: int, annual_miles: int = 12000) -> float:
    dep = _table("depreciation")
    curve = dep["retained_by_age"].get(segment_of(car), dep["retained_by_age"]["midsize"])
    pct = curve.get(str(min(years, 8)), curve["8"])
    extra = max(0, annual_miles * years - dep["annual_miles_baseline"] * years)
    pct -= (extra / 10000) * dep["high_mileage_penalty_per_10k"]
    return round(price * max(0.05, pct), 2)


# --------------------------------------------------------------------------- #
# Total Cost of Ownership comparison: buy-new vs CPO vs lease
# --------------------------------------------------------------------------- #
def compare_tco(
    car: dict[str, Any], *, years: int = 5, credit_score: int | None = None,
    annual_miles: int = 12000, state: str = "OH", cpo_price: float | None = None,
) -> dict[str, Any]:
    """Side-by-side N-year total cost of ownership for the three paths."""
    oc = _table("ownership_costs")
    inc = _table("incentives")
    msrp = float(car.get("msrp") or 0)
    running = lambda value_start: sum(
        annual_maintenance(car, y) + annual_insurance(car, value_start) +
        annual_fuel(car, annual_miles) + oc["registration_annual"]
        for y in range(years)
    )

    # Buy NEW
    rebate = inc["cash_rebate_new"].get(car.get("make"), inc["cash_rebate_new"]["_default"])
    new_price = max(0.0, msrp - rebate)
    new_loan = quote_loan(new_price, credit_score=credit_score, condition="new",
                          term_months=min(72, years * 12), state=state)
    new_resale = retained_value(car, new_price, years, annual_miles)
    new_running = running(new_price)
    new_total = new_loan["total_of_payments"] + new_running - new_resale

    # CPO (assume ~2-year-old certified unit)
    cpo = cpo_price or retained_value(car, msrp, 2)
    cpo_warranty = inc["cpo_warranty_value"].get(brand_tier(car.get("make")), inc["cpo_warranty_value"]["_default"])
    cpo_loan = quote_loan(cpo, credit_score=credit_score, condition="cpo",
                          term_months=min(72, years * 12), state=state)
    cpo_resale = retained_value(car, msrp, years + 2, annual_miles)
    cpo_running = running(cpo)
    cpo_total = cpo_loan["total_of_payments"] + cpo_running - cpo_resale - cpo_warranty

    # LEASE (chained 36-mo leases to cover the window; no resale, no maintenance risk)
    lease = quote_lease(car, credit_score=credit_score, term_months=36, annual_miles=annual_miles)
    n_leases = max(1, round(years * 12 / 36))
    lease_running = sum(annual_insurance(car, msrp) + annual_fuel(car, annual_miles) +
                        oc["registration_annual"] for _ in range(years))
    lease_total = lease["total_cost"] * n_leases + lease_running

    options = {
        "buy_new": {"upfront": new_loan["down_payment"], "monthly": new_loan["monthly_payment"],
                    "resale_value": new_resale, "running_costs": round(new_running, 2),
                    "net_cost": round(new_total, 2), "detail": new_loan},
        "buy_cpo": {"price": round(cpo, 2), "upfront": cpo_loan["down_payment"],
                    "monthly": cpo_loan["monthly_payment"], "resale_value": cpo_resale,
                    "warranty_value": cpo_warranty, "running_costs": round(cpo_running, 2),
                    "net_cost": round(cpo_total, 2), "detail": cpo_loan},
        "lease":   {"monthly": lease["monthly_payment"], "leases_needed": n_leases,
                    "running_costs": round(lease_running, 2), "resale_value": 0,
                    "net_cost": round(lease_total, 2), "detail": lease},
    }
    best = min(options, key=lambda k: options[k]["net_cost"])
    return {
        "vehicle": f"{car.get('year','')} {car.get('make','')} {car.get('model','')}".strip(),
        "years": years, "annual_miles": annual_miles,
        "credit_tier": credit_tier_from_score(credit_score),
        "options": options, "recommended": best,
        "note": "Synthetic demo figures — for illustration, not real quotes.",
    }


# --------------------------------------------------------------------------- #
# Rental: inventory generation + quote
# --------------------------------------------------------------------------- #
_RENTAL_CLASS = {"economy": "Economy", "midsize": "Standard", "suv": "SUV",
                 "truck": "Truck", "luxury": "Luxury", "performance": "Sport"}


def rental_locations() -> list[dict[str, Any]]:
    return _table("rental_locations")["locations"]


def daily_rate(car: dict[str, Any], location_id: str) -> float:
    """Deterministic daily rate = MSRP-derived base * branch multiplier."""
    msrp = float(car.get("msrp") or 0)
    base = msrp * 0.0008 + 18
    seg = segment_of(car)
    if seg in ("suv", "truck"):
        base *= 1.1
    elif seg in ("luxury", "performance"):
        base *= 1.4
    loc = next((l for l in rental_locations() if l["id"] == location_id), None)
    mult = loc["daily_rate_multiplier"] if loc else 1.0
    return float(max(29, round(base * mult / 5) * 5))


def build_rental_inventory(cars: list[dict[str, Any]], location_id: str) -> list[dict[str, Any]]:
    """Turn catalog cars into rentable units at a branch (deterministic subset)."""
    from .store import estimate_seats
    loc = next((l for l in rental_locations() if l["id"] == location_id), None)
    fleet_cap = loc["fleet_size"] if loc else 30
    units = []
    for car in cars:
        vid = str(car.get("id"))
        if _stable_hash("fleet", location_id, vid) % 10 < 6:  # ~60% offered at branch
            seg = segment_of(car)
            units.append({
                "unit_id": f"{location_id}-{vid}",
                "vehicle_id": vid,
                "label": f"{car.get('year','')} {car.get('make','')} {car.get('model','')}".strip(),
                "rental_class": _RENTAL_CLASS.get(seg, "Standard"),
                "seats": estimate_seats(car.get("vehicle_style")),
                "daily_rate": daily_rate(car, location_id),
                "units_available": 1 + _stable_hash("avail", location_id, vid) % 5,
            })
        if len(units) >= fleet_cap:
            break
    return units


def is_available(unit_id: str, pickup: str, dropoff: str) -> bool:
    """Deterministic availability for a date range (demo — most units are free)."""
    return _stable_hash("hold", unit_id, pickup, dropoff) % 10 != 0  # ~90% available


def quote_rental(
    car: dict[str, Any], location_id: str, *, days: int,
    addons: dict[str, int] | None = None, protection: list[str] | None = None,
    driver_age: int = 30, airport: bool | None = None,
) -> dict[str, Any]:
    """Rental price breakdown: base + add-ons + protection + fees + tax."""
    ra = _table("rental_addons")
    loc = next((l for l in rental_locations() if l["id"] == location_id), None)
    rate = daily_rate(car, location_id)
    base = rate * days
    addons = addons or {}
    protection = protection or []

    addon_by_code = {a["code"]: a for a in ra["addons"]}
    prot_by_code = {p["code"]: p for p in ra["protection"]}
    lines: list[dict[str, Any]] = [{"item": "Base rate", "detail": f"${rate}/day x {days}", "amount": round(base, 2)}]

    for code, qty in addons.items():
        if code in addon_by_code and qty > 0:
            a = addon_by_code[code]
            qty = min(qty, a["max_qty"])
            amt = a["price"] * qty * days
            lines.append({"item": a["label"], "detail": f"{qty} x ${a['price']}/day x {days}", "amount": round(amt, 2)})
    if driver_age < ra["fees"]["young_renter_age_threshold"]:
        yd = addon_by_code["young_driver"]
        lines.append({"item": yd["label"], "detail": f"${yd['price']}/day x {days}", "amount": round(yd["price"] * days, 2)})
    for code in protection:
        if code in prot_by_code:
            p = prot_by_code[code]
            lines.append({"item": p["label"], "detail": f"${p['price']}/day x {days}", "amount": round(p["price"] * days, 2)})

    subtotal = sum(l["amount"] for l in lines)
    is_airport = airport if airport is not None else (loc and "AIR" in loc["id"])
    if is_airport:
        conc = subtotal * ra["fees"]["airport_concession_pct"]
        lines.append({"item": "Airport concession fee", "detail": f"{ra['fees']['airport_concession_pct']*100:.0f}%", "amount": round(conc, 2)})
        subtotal += conc
    tax = subtotal * _table("finance_rates")["sales_tax_pct_by_state"].get(
        loc["state"] if loc else "OH", 0.07)
    total = subtotal + tax
    return {
        "location_id": location_id, "days": days, "daily_rate": rate,
        "line_items": lines, "subtotal": round(subtotal, 2),
        "tax": round(tax, 2), "total": round(total, 2),
        "total_per_day": round(total / max(1, days), 2),
        "note": "Synthetic demo figures.",
    }


# --------------------------------------------------------------------------- #
# Dealer handoff + test-drive scheduling (buy path)
# --------------------------------------------------------------------------- #
def assign_dealer(car: dict[str, Any]) -> dict[str, Any]:
    dealers = _table("dealers")["dealers"]
    idx = _stable_hash("dealer", car.get("id")) % len(dealers)
    return dealers[idx]


def test_drive_slots(car: dict[str, Any], *, count: int = 4, start: date | None = None) -> list[str]:
    td = _table("dealers")["test_drive"]
    start = (start or date.today()) + timedelta(days=td["lead_time_days"])
    slots: list[str] = []
    day = start
    seed = _stable_hash("slot", car.get("id"))
    while len(slots) < count:
        if day.strftime("%a") in td["open_days"]:
            times = td["slots_per_day"]
            t = times[(seed + day.toordinal()) % len(times)]
            slots.append(f"{day.isoformat()} {t}")
        day += timedelta(days=1)
    return slots


# --------------------------------------------------------------------------- #
# Persistence: rental bookings + test-drive appointments (same SQLite ledger)
# --------------------------------------------------------------------------- #
_EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS rental_bookings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id   TEXT NOT NULL,
    location_id  TEXT NOT NULL,
    label        TEXT NOT NULL,
    pickup       TEXT NOT NULL,
    dropoff      TEXT NOT NULL,
    days         INTEGER NOT NULL,
    addons       TEXT,
    protection   TEXT,
    total        REAL NOT NULL,
    customer     TEXT,
    confirmation TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS test_drive_appointments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id   TEXT NOT NULL,
    label        TEXT NOT NULL,
    dealer_id    TEXT NOT NULL,
    slot         TEXT NOT NULL,
    customer     TEXT,
    confirmation TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _conn() -> sqlite3.Connection:
    conn = _store_conn()
    conn.executescript(_EXTRA_SCHEMA)
    return conn


def _confirmation(prefix: str, *parts: Any) -> str:
    return f"{prefix}-{_stable_hash(datetime.now().isoformat(), *parts) % 1000000:06d}"


def book_rental(
    car: dict[str, Any], location_id: str, *, pickup: str, dropoff: str, days: int,
    total: float, addons: dict[str, int] | None = None,
    protection: list[str] | None = None, customer: str | None = None,
) -> dict[str, Any]:
    label = f"{car.get('year','')} {car.get('make','')} {car.get('model','')}".strip()
    conf = _confirmation("RENT", car.get("id"), pickup, dropoff)
    conn = _conn()
    try:
        cur = conn.execute(
            """INSERT INTO rental_bookings
               (vehicle_id, location_id, label, pickup, dropoff, days, addons, protection, total, customer, confirmation)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [str(car.get("id")), location_id, label, pickup, dropoff, days,
             json.dumps(addons or {}), json.dumps(protection or []), total, customer, conf],
        )
        conn.commit()
        return {"booking_id": cur.lastrowid, "confirmation": conf, "label": label,
                "location_id": location_id, "pickup": pickup, "dropoff": dropoff,
                "days": days, "total": total}
    finally:
        conn.close()


def list_rental_bookings(limit: int = 100) -> list[dict[str, Any]]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM rental_bookings ORDER BY id DESC LIMIT ?", [limit]
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def list_test_drive_appointments(limit: int = 100) -> list[dict[str, Any]]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM test_drive_appointments ORDER BY id DESC LIMIT ?", [limit]
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def book_test_drive(car: dict[str, Any], dealer: dict[str, Any], slot: str,
                    customer: str | None = None) -> dict[str, Any]:
    label = f"{car.get('year','')} {car.get('make','')} {car.get('model','')}".strip()
    conf = _confirmation("TD", car.get("id"), slot)
    conn = _conn()
    try:
        cur = conn.execute(
            """INSERT INTO test_drive_appointments
               (vehicle_id, label, dealer_id, slot, customer, confirmation)
               VALUES (?,?,?,?,?,?)""",
            [str(car.get("id")), label, dealer["id"], slot, customer, conf],
        )
        conn.commit()
        return {"appointment_id": cur.lastrowid, "confirmation": conf, "label": label,
                "dealer": dealer, "slot": slot}
    finally:
        conn.close()
