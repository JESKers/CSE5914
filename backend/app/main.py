"""FastAPI entrypoint — wires the API contract to the search core + RAG parser.

Owner: Eric (Integration). Run from the repo root:
    uvicorn backend.app.main:app --reload

Endpoints (see docs/API_CONTRACT.md):
    GET  /health
    GET  /search     structured filters + keyword
    GET  /facets     dropdown buckets
    POST /recommend  free-text natural-language query (RAG spike)

Additive Buy/Rent store + NHTSA vPIC endpoints (see docs/STORE_VPIC.md):
    GET  /store/listings        priced/stocked cars, mode=buy|rent
    GET  /store/vehicle/{id}    one listing
    POST /store/orders          purchase or rent a vehicle
    GET  /store/orders          order history
    GET  /vpic/decode/{vin}     live VIN decode via vPIC
    GET  /vpic/models           live models for a make/year via vPIC
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from search import search_service, vpic

from . import store, synth
from .config import settings
from .es_client import get_es
from .schemas import (
    AssistantBookingsResponse,
    CarResult,
    ChatRequest,
    ChatResponse,
    FacetsResponse,
    ListingResult,
    ListingsResponse,
    ModelsResponse,
    OrderRequest,
    OrderResponse,
    OrdersResponse,
    RecommendRequest,
    RecommendResponse,
    SearchFilters,
    SearchResponse,
    VpicDecodeResponse,
    VpicModelsResponse,
)

app = FastAPI(title="JESKers Car Search", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _to_results(rows: list[dict]) -> list[CarResult]:
    return [CarResult(**row) for row in rows]


def _validate_ranges(f: SearchFilters) -> None:
    """Reject inverted min/max ranges with a 400 (per the API contract)."""
    for lo, hi, name in (
        (f.year_min, f.year_max, "year"),
        (f.price_min, f.price_max, "price"),
        (f.hp_min, f.hp_max, "hp"),
    ):
        if lo is not None and hi is not None and lo > hi:
            raise HTTPException(400, f"{name}_min ({lo}) must not exceed {name}_max ({hi})")


@app.get("/health")
def health():
    try:
        ok = get_es().ping()
    except Exception:
        ok = False
    return {"status": "ok", "elasticsearch": ok}


@app.get("/search", response_model=SearchResponse)
def search(
    make: str | None = None,
    model: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    hp_min: int | None = None,
    hp_max: int | None = None,
    engine_fuel_type: str | None = None,
    transmission_type: str | None = None,
    q: str | None = None,
    sort: str = "popularity",
    order: str = "desc",
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    filters = SearchFilters(
        make=make, model=model, year_min=year_min, year_max=year_max,
        price_min=price_min, price_max=price_max, hp_min=hp_min, hp_max=hp_max,
        engine_fuel_type=engine_fuel_type, transmission_type=transmission_type,
        q=q, sort=sort, order=order, page=page, size=size,
    )
    _validate_ranges(filters)
    res = search_service.search(filters)
    return SearchResponse(
        results=_to_results(res["results"]),
        total=res["total"],
        page=res["page"],
        size=res["size"],
        query_echo=filters.model_dump(exclude_none=True),
    )


@app.get("/facets", response_model=FacetsResponse)
def facets():
    return FacetsResponse(**search_service.facets())


@app.get("/models", response_model=ModelsResponse)
def models(make: str = Query(..., min_length=1, description="make to list models for")):
    """Distinct models for a make — populates the dependent Model dropdown."""
    return ModelsResponse(make=make, models=search_service.models(make))


@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest):
    """Free-text natural-language recommendation (RAG/LLM spike, Timebox 3 prep)."""
    if not settings.anthropic_api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY not configured")
    from rag.parser import parse_query  # lazy import: only /recommend needs anthropic

    filters = parse_query(req.query)
    res = search_service.search(filters)
    return RecommendResponse(
        results=_to_results(res["results"]),
        total=res["total"],
        query_echo={"query": req.query, "parsed_filters": filters.model_dump(exclude_none=True)},
    )


# =========================================================================== #
# Buy / Rent store (additive — does not touch the frozen contract above)
# =========================================================================== #
@app.get("/store/listings", response_model=ListingsResponse)
def store_listings(
    mode: str = Query("buy", description="'buy' or 'rent'"),
    make: str | None = None,
    model: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    hp_min: int | None = None,
    hp_max: int | None = None,
    engine_fuel_type: str | None = None,
    transmission_type: str | None = None,
    q: str | None = None,
    sort: str = "popularity",
    order: str = "desc",
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """Catalog cars priced and stocked for purchase or rental.

    Reuses the search core for filtering/pagination, then augments each hit with
    buy_price / rent_daily / seats / availability + vPIC brand verification. In
    rent mode the price bounds are interpreted as daily-rent and converted to an
    approximate MSRP range so ES still drives pagination/totals.
    """
    if mode not in ("buy", "rent"):
        raise HTTPException(400, "mode must be 'buy' or 'rent'")

    es_price_min, es_price_max = price_min, price_max
    if mode == "rent":
        es_price_min = store.rent_daily_to_msrp(price_min) if price_min is not None else None
        es_price_max = store.rent_daily_to_msrp(price_max) if price_max is not None else None

    filters = SearchFilters(
        make=make, model=model, year_min=year_min, year_max=year_max,
        price_min=es_price_min, price_max=es_price_max, hp_min=hp_min, hp_max=hp_max,
        engine_fuel_type=engine_fuel_type, transmission_type=transmission_type,
        q=q, sort=sort, order=order, page=page, size=size,
    )
    _validate_ranges(filters)
    res = search_service.search(filters)

    verified_makes = vpic.make_id_index()  # cached; offline -> {}
    sold = store.purchases_by_vehicle()
    listings = []
    for car in res["results"]:
        verified = str(car.get("make", "")).upper() in verified_makes
        listing = store.to_listing(car, verified=verified, sold=sold.get(str(car["id"]), 0))
        if mode == "rent" and not listing["for_rent"]:
            continue  # only show rentable units in rent mode
        listings.append(ListingResult(**listing))

    echo = {k: v for k, v in {
        "mode": mode, "make": make, "model": model, "q": q,
        "price_min": price_min, "price_max": price_max, "sort": sort, "order": order,
    }.items() if v is not None}
    return ListingsResponse(
        results=listings, total=res["total"], mode=mode,
        page=res["page"], size=res["size"], query_echo=echo,
    )


@app.get("/store/vehicle/{vehicle_id}", response_model=ListingResult)
def store_vehicle(vehicle_id: str):
    car = search_service.get_car(vehicle_id)
    if not car:
        raise HTTPException(404, "Vehicle not found")
    verified = vpic.is_verified(str(car.get("make", "")))
    sold = store.purchases_by_vehicle().get(str(vehicle_id), 0)
    return ListingResult(**store.to_listing(car, verified=verified, sold=sold))


@app.post("/store/orders", response_model=OrderResponse)
def store_create_order(req: OrderRequest):
    if req.mode not in ("buy", "rent"):
        raise HTTPException(400, "mode must be 'buy' or 'rent'")
    car = search_service.get_car(req.vehicle_id)
    if not car:
        raise HTTPException(404, "Vehicle not found")

    sold = store.purchases_by_vehicle().get(str(req.vehicle_id), 0)
    listing = store.to_listing(car, verified=False, sold=sold)
    label = f"{car.get('year')} {car.get('make')} {car.get('model')}"

    if req.mode == "buy":
        if listing["stock"] <= 0:
            raise HTTPException(409, "Out of stock for purchase")
        total = listing["buy_price"]
        message = f"Purchase confirmed for {label} at ${total:,.0f}."
    else:
        if not listing["for_rent"]:
            raise HTTPException(409, "Vehicle not available for rent")
        days = req.rent_days or 1
        total = listing["rent_daily"] * days
        message = f"Rental confirmed for {label}: {days} day(s) at ${total:,.0f}."

    order_id = store.record_order(
        vehicle_id=str(req.vehicle_id), label=label, mode=req.mode,
        total=total, rent_days=req.rent_days, customer=req.customer,
    )
    return OrderResponse(
        order_id=order_id, vehicle=label, mode=req.mode,
        rent_days=req.rent_days, total=total, message=message,
    )


@app.get("/store/orders", response_model=OrdersResponse)
def store_order_history():
    return OrdersResponse(orders=store.list_orders())


# =========================================================================== #
# Buy/Rent AI assistant (additive — agentic chat over the store + synth layers)
# =========================================================================== #
@app.post("/assistant/chat", response_model=ChatResponse)
def assistant_chat(req: ChatRequest):
    """One conversational turn with the buy/rent agent.

    The agent runs a Claude tool-use loop (see backend/app/agent.py): rentals
    are handled end-to-end (search -> add-ons -> insurance -> booking with a
    confirmation number); purchases get TCO/finance analysis, a test-drive
    appointment and a dealer handoff. Conversation state is held server-side
    per session_id.
    """
    if not settings.anthropic_api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY not configured")
    from . import agent  # lazy import: only /assistant needs anthropic

    session_id = req.session_id or agent.new_session_id()
    try:
        result = agent.chat(session_id, req.message)
    except Exception as exc:
        raise HTTPException(502, f"Assistant unavailable: {exc}")
    return ChatResponse(session_id=session_id, reply=result["reply"], events=result["events"])


@app.delete("/assistant/chat/{session_id}")
def assistant_reset(session_id: str):
    """Drop a conversation so the next message starts a fresh session."""
    from . import agent

    agent.reset_session(session_id)
    return {"status": "reset", "session_id": session_id}


@app.get("/assistant/bookings", response_model=AssistantBookingsResponse)
def assistant_bookings():
    """Rental bookings + test-drive appointments the agent has confirmed."""
    return AssistantBookingsResponse(
        rentals=synth.list_rental_bookings(),
        test_drives=synth.list_test_drive_appointments(),
    )


# =========================================================================== #
# NHTSA vPIC live endpoints (catalog source / enrichment)
# =========================================================================== #
@app.get("/vpic/decode/{vin}", response_model=VpicDecodeResponse)
def vpic_decode(vin: str, year: int | None = None):
    """Decode a VIN via the NHTSA vPIC API."""
    decoded = vpic.decode_vin(vin, year)
    if not decoded:
        raise HTTPException(502, "vPIC decode unavailable")
    keep = {
        "Make", "Model", "ModelYear", "BodyClass", "VehicleType", "Doors",
        "FuelTypePrimary", "DisplacementL", "EngineCylinders", "DriveType",
        "Manufacturer", "PlantCountry", "Series", "Trim",
    }
    summary = {k: v for k, v in decoded.items() if k in keep and v}
    return VpicDecodeResponse(vin=vin, summary=summary, raw=decoded)


@app.get("/vpic/models", response_model=VpicModelsResponse)
def vpic_models(make: str = Query(..., min_length=1), year: int | None = None):
    """Model list for a make from vPIC.

    Without a year, answers from the local snapshot (data/vpic_models.json, built
    by `python -m search.fetch_vpic_models`) so catalog makes resolve instantly
    and offline; falls back to a live vPIC call when the make isn't snapshotted or
    a specific model year is requested.
    """
    if year is None:
        snapshot = vpic.snapshot_models_for_make(make)
        if snapshot is not None:
            return VpicModelsResponse(make=make, year=None, count=len(snapshot), models=snapshot)

    models_ = vpic.get_models_for_make(make, year)
    return VpicModelsResponse(
        make=make, year=year, count=len(models_),
        models=[m.get("Model_Name") for m in models_ if m.get("Model_Name")],
    )
