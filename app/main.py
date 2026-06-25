"""JESKers — Smart Car Recommendation, Purchase & Rental API.

Catalog data is backed by the NHTSA vPIC API (verified brands + live specs/VIN
decode) joined with MSRP pricing from data.csv. Customers can filter the catalog
by brand, price, body style, fuel and more, then purchase or rent a vehicle.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db, recommend, vpic

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"

app = FastAPI(
    title="JESKers — Smart Car Recommendation, Purchase & Rental API",
    description="Filter, recommend, buy and rent vehicles. Catalog backed by the "
    "NHTSA vPIC API joined with MSRP pricing.",
    version="2.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    count = db.seed()
    app.state.vehicle_count = count


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _row_to_dict(row) -> dict[str, Any]:
    d = dict(row)
    d["vpic_verified"] = d.get("vpic_make_id") is not None
    return d


# --------------------------------------------------------------------------- #
# Health & meta
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health() -> dict[str, Any]:
    conn = db.get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
    finally:
        conn.close()
    return {"status": "ok", "vehicles": count, "catalog_source": "data.csv + vPIC"}


@app.get("/api/makes")
def makes() -> dict[str, Any]:
    """Brand directory: catalog makes, flagged where verified against vPIC."""
    conn = db.get_conn()
    try:
        rows = conn.execute(
            """SELECT make, COUNT(*) AS count, MIN(buy_price) AS min_price,
                      MAX(buy_price) AS max_price, vpic_make_id
               FROM vehicles GROUP BY make ORDER BY make"""
        ).fetchall()
    finally:
        conn.close()
    return {
        "makes": [
            {
                "make": r["make"],
                "count": r["count"],
                "min_price": r["min_price"],
                "max_price": r["max_price"],
                "vpic_make_id": r["vpic_make_id"],
                "vpic_verified": r["vpic_make_id"] is not None,
            }
            for r in rows
        ]
    }


@app.get("/api/filters")
def filters() -> dict[str, Any]:
    """Facet values + price ranges to populate the filter UI."""
    conn = db.get_conn()
    try:
        def distinct(col: str) -> list[str]:
            rows = conn.execute(
                f"SELECT DISTINCT {col} AS v FROM vehicles WHERE {col} != '' ORDER BY {col}"
            ).fetchall()
            return [r["v"] for r in rows]

        price = conn.execute(
            "SELECT MIN(buy_price) AS lo, MAX(buy_price) AS hi FROM vehicles"
        ).fetchone()
        rent = conn.execute(
            "SELECT MIN(rent_daily) AS lo, MAX(rent_daily) AS hi FROM vehicles"
        ).fetchone()
        years = conn.execute(
            "SELECT MIN(year) AS lo, MAX(year) AS hi FROM vehicles"
        ).fetchone()
        return {
            "makes": distinct("make"),
            "body_styles": distinct("body_style"),
            "fuel_types": distinct("fuel_type"),
            "sizes": distinct("size"),
            "drives": distinct("drive"),
            "buy_price": {"min": price["lo"], "max": price["hi"]},
            "rent_daily": {"min": rent["lo"], "max": rent["hi"]},
            "years": {"min": years["lo"], "max": years["hi"]},
        }
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Catalog search / filtering
# --------------------------------------------------------------------------- #
@app.get("/api/vehicles")
def list_vehicles(
    make: str | None = None,
    body_style: str | None = None,
    fuel_type: str | None = None,
    size: str | None = None,
    drive: str | None = None,
    mode: Literal["buy", "rent"] = "buy",
    min_price: int | None = None,
    max_price: int | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    min_seats: int | None = None,
    q: str | None = Query(None, description="free-text match on make/model"),
    sort: Literal["price_asc", "price_desc", "year_desc", "popularity", "mpg"] = "popularity",
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
) -> dict[str, Any]:
    price_col = "rent_daily" if mode == "rent" else "buy_price"
    where: list[str] = []
    params: list[Any] = []

    if mode == "rent":
        where.append("for_rent = 1")
    else:
        where.append("for_sale = 1")
    if make:
        where.append("make = ?")
        params.append(make)
    if body_style:
        where.append("body_style = ?")
        params.append(body_style)
    if fuel_type:
        where.append("fuel_type = ?")
        params.append(fuel_type)
    if size:
        where.append("size = ?")
        params.append(size)
    if drive:
        where.append("drive = ?")
        params.append(drive)
    if min_price is not None:
        where.append(f"{price_col} >= ?")
        params.append(min_price)
    if max_price is not None:
        where.append(f"{price_col} <= ?")
        params.append(max_price)
    if year_min is not None:
        where.append("year >= ?")
        params.append(year_min)
    if year_max is not None:
        where.append("year <= ?")
        params.append(year_max)
    if min_seats is not None:
        where.append("seats >= ?")
        params.append(min_seats)
    if q:
        where.append("(make LIKE ? OR model LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    sort_sql = {
        "price_asc": f"{price_col} ASC",
        "price_desc": f"{price_col} DESC",
        "year_desc": "year DESC",
        "popularity": "popularity DESC",
        "mpg": "mpg_hwy DESC",
    }[sort]

    where_sql = " AND ".join(where) or "1=1"
    conn = db.get_conn()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM vehicles WHERE {where_sql}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"""SELECT * FROM vehicles WHERE {where_sql}
                ORDER BY {sort_sql}, popularity DESC
                LIMIT ? OFFSET ?""",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()
    finally:
        conn.close()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "mode": mode,
        "results": [_row_to_dict(r) for r in rows],
    }


@app.get("/api/vehicles/{vehicle_id}")
def get_vehicle(vehicle_id: int) -> dict[str, Any]:
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM vehicles WHERE id = ?", [vehicle_id]
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "Vehicle not found")
    return _row_to_dict(row)


@app.get("/api/vehicles/{vehicle_id}/vpic")
def vehicle_vpic(vehicle_id: int) -> dict[str, Any]:
    """Live vPIC enrichment for a catalog vehicle (vehicle types + models)."""
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT make, model, year FROM vehicles WHERE id = ?", [vehicle_id]
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "Vehicle not found")
    types = vpic.get_vehicle_types_for_make(row["make"])
    models = vpic.get_models_for_make(row["make"], row["year"])
    return {
        "make": row["make"],
        "model": row["model"],
        "year": row["year"],
        "vpic_vehicle_types": [t.get("VehicleTypeName") for t in types],
        "vpic_models_count": len(models),
        "vpic_models_sample": [m.get("Model_Name") for m in models[:25]],
    }


# --------------------------------------------------------------------------- #
# Live vPIC passthrough endpoints
# --------------------------------------------------------------------------- #
@app.get("/api/vpic/models")
def vpic_models(make: str, year: int | None = None) -> dict[str, Any]:
    models = vpic.get_models_for_make(make, year)
    return {
        "make": make,
        "year": year,
        "count": len(models),
        "models": [m.get("Model_Name") for m in models],
    }


@app.get("/api/vpic/decode/{vin}")
def vpic_decode(vin: str, year: int | None = None) -> dict[str, Any]:
    decoded = vpic.decode_vin(vin, year)
    if not decoded:
        raise HTTPException(502, "vPIC decode unavailable")
    keep = {
        "Make", "Model", "ModelYear", "BodyClass", "VehicleType", "Doors",
        "FuelTypePrimary", "DisplacementL", "EngineCylinders", "DriveType",
        "Manufacturer", "PlantCountry", "Series", "Trim",
    }
    summary = {k: v for k, v in decoded.items() if k in keep and v}
    return {"vin": vin, "summary": summary, "raw": decoded}


# --------------------------------------------------------------------------- #
# Recommendation
# --------------------------------------------------------------------------- #
class RecommendRequest(BaseModel):
    mode: Literal["buy", "rent"] = "buy"
    budget_max: int | None = Field(None, description="max purchase price or daily rent")
    make: str | None = None
    body_style: str | None = None
    fuel_type: str | None = None
    min_seats: int | None = None
    priorities: list[Literal["efficiency", "performance", "price"]] = []
    limit: int = Field(8, ge=1, le=50)


@app.post("/api/recommend")
def recommend_vehicles(req: RecommendRequest) -> dict[str, Any]:
    price_col = "rent_daily" if req.mode == "rent" else "buy_price"
    where = ["for_rent = 1" if req.mode == "rent" else "for_sale = 1"]
    params: list[Any] = []
    if req.make:
        where.append("make = ?")
        params.append(req.make)
    if req.body_style:
        where.append("body_style = ?")
        params.append(req.body_style)
    if req.fuel_type:
        where.append("fuel_type = ?")
        params.append(req.fuel_type)
    # Pull a generous candidate pool (within ~1.5x budget) then score.
    if req.budget_max:
        where.append(f"{price_col} <= ?")
        params.append(int(req.budget_max * 1.5))

    conn = db.get_conn()
    try:
        rows = conn.execute(
            f"SELECT * FROM vehicles WHERE {' AND '.join(where)} "
            f"ORDER BY popularity DESC LIMIT 400",
            params,
        ).fetchall()
    finally:
        conn.close()

    prefs = req.model_dump()
    scored = []
    for r in rows:
        d = _row_to_dict(r)
        s, reasons = recommend.score_vehicle(d, prefs)
        d["match_score"] = s
        d["reasons"] = reasons
        scored.append(d)
    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return {"mode": req.mode, "count": len(scored[: req.limit]), "results": scored[: req.limit]}


# --------------------------------------------------------------------------- #
# Purchase / rent (orders)
# --------------------------------------------------------------------------- #
class OrderRequest(BaseModel):
    vehicle_id: int
    mode: Literal["buy", "rent"]
    rent_days: int | None = Field(None, ge=1, le=365)
    customer: str | None = None


@app.post("/api/orders")
def create_order(req: OrderRequest) -> dict[str, Any]:
    conn = db.get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM vehicles WHERE id = ?", [req.vehicle_id]
        ).fetchone()
        if not row:
            raise HTTPException(404, "Vehicle not found")

        if req.mode == "buy":
            if not row["for_sale"] or row["stock"] <= 0:
                raise HTTPException(409, "Vehicle not available for purchase")
            total = row["buy_price"]
            conn.execute(
                "UPDATE vehicles SET stock = stock - 1 WHERE id = ?", [req.vehicle_id]
            )
        else:  # rent
            if not row["for_rent"]:
                raise HTTPException(409, "Vehicle not available for rent")
            days = req.rent_days or 1
            total = row["rent_daily"] * days

        cur = conn.execute(
            """INSERT INTO orders (vehicle_id, mode, rent_days, total, customer)
               VALUES (?,?,?,?,?)""",
            [req.vehicle_id, req.mode, req.rent_days, total, req.customer],
        )
        conn.commit()
        order_id = cur.lastrowid
    finally:
        conn.close()

    label = (
        f"{row['year']} {row['make']} {row['model']}"
    )
    return {
        "order_id": order_id,
        "vehicle": label,
        "mode": req.mode,
        "rent_days": req.rent_days,
        "total": total,
        "status": "confirmed",
        "message": (
            f"Purchase confirmed for {label} at ${total:,}."
            if req.mode == "buy"
            else f"Rental confirmed for {label}: {req.rent_days or 1} day(s) at ${total:,}."
        ),
    }


@app.get("/api/orders")
def list_orders() -> dict[str, Any]:
    conn = db.get_conn()
    try:
        rows = conn.execute(
            """SELECT o.*, v.make, v.model, v.year
               FROM orders o JOIN vehicles v ON v.id = o.vehicle_id
               ORDER BY o.id DESC LIMIT 100"""
        ).fetchall()
    finally:
        conn.close()
    return {"orders": [dict(r) for r in rows]}


# --------------------------------------------------------------------------- #
# Static frontend (mounted last so /api/* wins)
# --------------------------------------------------------------------------- #
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
