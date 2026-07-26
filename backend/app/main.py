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
import logging
import time
import uuid

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
    RecommendationResult,
    SearchFilters,
    SearchResponse,
    VpicDecodeResponse,
    VpicModelsResponse,
)

app = FastAPI(title="JESKers Car Search", version="0.1.0")
logger = logging.getLogger(__name__)

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
    """Return Elasticsearch-grounded recommendations with verifiable reasons."""
    from rag.parser import parse_query  # lazy import: only /recommend needs the local parser
    from rag.grounded_recommend import enrich_with_vpic, generate_grounded_summary

    request_id = uuid.uuid4().hex
    started = time.perf_counter()
    filters = parse_query(req.query)
    parsed_at = time.perf_counter()
    conflicts = _filter_conflicts(filters)
    if conflicts:
        narrative = "The request contains contradictory hard constraints: " + "; ".join(conflicts)
        return RecommendResponse(
            results=[], alternatives=[], total=0,
            query_echo={"query": req.query, "parsed_filters": filters.model_dump(exclude_none=True)},
            message="Resolve the contradictory constraints before searching.",
            narrative=narrative, generation_mode="deterministic",
            sources=["Elasticsearch vehicle catalog", "NHTSA vPIC"],
            warnings=conflicts + _unsupported_warnings(filters),
            request_id=request_id,
            timings_ms={"parse": round((parsed_at - started) * 1000, 3)},
        )

    search_started = time.perf_counter()
    res = search_service.search(filters)
    searched_at = time.perf_counter()
    grounded = []
    for row in res["results"]:
        if not _satisfies_hard_constraints(row, filters):
            continue
        grounded.append(RecommendationResult(
            **row,
            match_reasons=_recommendation_reasons(row, filters),
        ))

    alternatives, relaxation_warnings = ([], [])
    if not grounded:
        alternatives, relaxation_warnings = _relaxed_recommendations(filters)

    narrative_input = grounded or alternatives
    enriched = enrich_with_vpic([item.model_dump() for item in narrative_input])
    narrative_input = [RecommendationResult(**item) for item in enriched]
    if grounded:
        grounded = narrative_input
    else:
        alternatives = narrative_input
    narrative, generation_mode, structured = generate_grounded_summary(
        req.query, [item.model_dump() for item in narrative_input]
    )
    message = (
        f"Found {len(grounded)} vehicles that satisfy the extracted hard constraints."
        if grounded
        else "No exact matches were found; clearly labeled near matches are shown separately."
    )
    finished = time.perf_counter()
    timings = {
        "parse": round((parsed_at - started) * 1000, 3),
        "elasticsearch": round((searched_at - search_started) * 1000, 3),
        "enrichment_and_generation": round((finished - searched_at) * 1000, 3),
        "total": round((finished - started) * 1000, 3),
    }
    logged_filters = filters.model_dump(exclude_none=True)
    logged_filters.pop("q", None)  # free text may contain personal information
    logger.info(
        "recommendation_complete request_id=%s filters=%s exact=%d alternatives=%d "
        "vehicle_ids=%s generation=%s timings_ms=%s",
        request_id, logged_filters, len(grounded), len(alternatives),
        [item.id for item in narrative_input], generation_mode, timings,
    )
    return RecommendResponse(
        results=grounded,
        alternatives=alternatives,
        total=len(grounded),
        query_echo={"query": req.query, "parsed_filters": filters.model_dump(exclude_none=True)},
        message=message,
        narrative=narrative,
        generation_mode=generation_mode,
        sources=["Elasticsearch vehicle catalog", "NHTSA vPIC"],
        warnings=relaxation_warnings + _unsupported_warnings(filters),
        recommended_vehicle_ids=structured["recommended_vehicle_ids"],
        comparison_points=structured["comparison_points"],
        request_id=request_id,
        timings_ms=timings,
    )


def _filter_conflicts(filters: SearchFilters) -> list[str]:
    conflicts = []
    for low, high, label in (
        (filters.year_min, filters.year_max, "year"),
        (filters.price_min, filters.price_max, "price"),
        (filters.hp_min, filters.hp_max, "horsepower"),
        (filters.engine_cylinders_min, filters.engine_cylinders_max, "cylinder count"),
        (filters.number_of_doors_min, filters.number_of_doors_max, "door count"),
        (filters.city_mpg_min, filters.city_mpg_max, "city MPG"),
        (filters.highway_mpg_min, filters.highway_mpg_max, "highway MPG"),
        (filters.combined_mpg_min, filters.combined_mpg_max, "combined MPG"),
    ):
        if low is not None and high is not None and low > high:
            conflicts.append(f"{label} minimum {low} exceeds maximum {high}")
    return conflicts


def _unsupported_warnings(filters: SearchFilters) -> list[str]:
    if not filters.unsupported_preferences:
        return []
    labels = ", ".join(filters.unsupported_preferences)
    return [
        "The catalog cannot directly verify these requested details: "
        f"{labels}. They were not used as hard filters."
    ]


def _relaxed_recommendations(filters: SearchFilters) -> tuple[list[RecommendationResult], list[str]]:
    """Find near matches by dropping one constraint, never mixing them with exact results."""
    relaxable = [
        "q", "price_max", "price_min", "hp_min", "hp_max", "year_min", "year_max",
        "transmission_type", "transmission_types", "engine_fuel_type", "powertrains",
        "make", "makes", "model", "models", "vehicle_styles", "vehicle_sizes",
        "driven_wheels", "market_categories", "engine_cylinders_min",
        "engine_cylinders_max", "number_of_doors_min", "number_of_doors_max",
        "city_mpg_min", "city_mpg_max", "highway_mpg_min", "highway_mpg_max",
        "combined_mpg_min", "combined_mpg_max",
    ]
    for field in relaxable:
        if getattr(filters, field) is None:
            continue
        relaxed = filters.model_copy(update={field: None, "page": 1, "size": 5})
        response = search_service.search(relaxed)
        candidates = [row for row in response["results"] if _satisfies_hard_constraints(row, relaxed)]
        if not candidates:
            continue
        label = "soft keyword preference" if field == "q" else field
        return [
            RecommendationResult(
                **row,
                match_reasons=_recommendation_reasons(row, relaxed),
                relaxed_constraints=[field],
            )
            for row in candidates[:5]
        ], [f"No exact matches; relaxed {label} for the alternatives below."]
    return [], ["No exact or single-constraint near matches were found."]


def _satisfies_hard_constraints(car: dict, filters: SearchFilters) -> bool:
    """Defensive check: never present a row that violates an extracted constraint."""
    checks = (
        (filters.make, car.get("make"), lambda actual, wanted: str(actual).lower() == str(wanted).lower()),
        (filters.model, car.get("model"), lambda actual, wanted: str(actual).lower() == str(wanted).lower()),
        (filters.year_min, car.get("year"), lambda actual, wanted: actual >= wanted),
        (filters.year_max, car.get("year"), lambda actual, wanted: actual <= wanted),
        (filters.price_min, car.get("msrp"), lambda actual, wanted: actual >= wanted),
        (filters.price_max, car.get("msrp"), lambda actual, wanted: actual <= wanted),
        (filters.hp_min, car.get("engine_hp"), lambda actual, wanted: actual >= wanted),
        (filters.hp_max, car.get("engine_hp"), lambda actual, wanted: actual <= wanted),
        (
            filters.engine_cylinders_min,
            car.get("engine_cylinders"),
            lambda actual, wanted: actual >= wanted,
        ),
        (
            filters.engine_cylinders_max,
            car.get("engine_cylinders"),
            lambda actual, wanted: actual <= wanted,
        ),
        (
            filters.number_of_doors_min,
            car.get("number_of_doors"),
            lambda actual, wanted: actual >= wanted,
        ),
        (
            filters.number_of_doors_max,
            car.get("number_of_doors"),
            lambda actual, wanted: actual <= wanted,
        ),
        (filters.city_mpg_min, car.get("city_mpg"), lambda actual, wanted: actual >= wanted),
        (filters.city_mpg_max, car.get("city_mpg"), lambda actual, wanted: actual <= wanted),
        (
            filters.highway_mpg_min,
            car.get("highway_mpg"),
            lambda actual, wanted: actual >= wanted,
        ),
        (
            filters.highway_mpg_max,
            car.get("highway_mpg"),
            lambda actual, wanted: actual <= wanted,
        ),
        (
            filters.combined_mpg_min,
            car.get("combined_mpg"),
            lambda actual, wanted: actual >= wanted,
        ),
        (
            filters.combined_mpg_max,
            car.get("combined_mpg"),
            lambda actual, wanted: actual <= wanted,
        ),
        (
            filters.transmission_type,
            car.get("transmission_type"),
            lambda actual, wanted: str(actual).lower() == str(wanted).lower(),
        ),
        (
            filters.engine_fuel_type,
            car.get("engine_fuel_type"),
            lambda actual, wanted: str(wanted).lower() in str(actual).lower(),
        ),
    )
    for wanted, actual, predicate in checks:
        if wanted is not None and (actual is None or not predicate(actual, wanted)):
            return False

    def matches_any(actual, wanted) -> bool:
        return any(str(actual).casefold() == str(value).casefold() for value in wanted or [])

    def contains_any(actual, wanted) -> bool:
        text = str(actual).casefold()
        return any(str(value).casefold() in text for value in wanted or [])

    for field, actual in (
        (filters.makes, car.get("make")),
        (filters.models, car.get("model")),
        (filters.transmission_types, car.get("transmission_type")),
        (filters.vehicle_styles, car.get("vehicle_style")),
        (filters.vehicle_sizes, car.get("vehicle_size")),
        (filters.driven_wheels, car.get("driven_wheels")),
    ):
        if field and (actual is None or not matches_any(actual, field)):
            return False
    if filters.market_categories and not contains_any(
        car.get("market_category"), filters.market_categories
    ):
        return False

    for field, actual in (
        (filters.excluded_makes, car.get("make")),
        (filters.excluded_models, car.get("model")),
        (filters.excluded_transmission_types, car.get("transmission_type")),
        (filters.excluded_vehicle_styles, car.get("vehicle_style")),
        (filters.excluded_driven_wheels, car.get("driven_wheels")),
    ):
        if field and actual is not None and matches_any(actual, field):
            return False
    if filters.excluded_market_categories and contains_any(
        car.get("market_category"), filters.excluded_market_categories
    ):
        return False
    if filters.powertrains and not any(
        _car_matches_powertrain(car, value) for value in filters.powertrains
    ):
        return False
    if filters.excluded_powertrains and any(
        _car_matches_powertrain(car, value) for value in filters.excluded_powertrains
    ):
        return False
    return True


def _car_matches_powertrain(car: dict, value: str) -> bool:
    fuel = str(car.get("engine_fuel_type", "")).casefold()
    category = str(car.get("market_category", "")).casefold()
    normalized = value.casefold()
    if normalized == "hybrid":
        return "hybrid" in category
    if normalized == "gasoline":
        return "unleaded" in fuel
    if normalized == "flex-fuel":
        return "flex-fuel" in fuel
    return normalized in fuel


def _recommendation_reasons(car: dict, filters: SearchFilters) -> list[str]:
    """Build explanations only from stored vehicle facts and applied filters."""
    reasons = []
    if filters.make:
        reasons.append(f"Matches requested make: {car['make']}")
    if filters.model:
        reasons.append(f"Matches requested model: {car['model']}")
    if filters.price_max is not None and car.get("msrp") is not None:
        reasons.append(f"MSRP ${car['msrp']:,.0f} is within the ${filters.price_max:,.0f} limit")
    if filters.year_min is not None and car.get("year") is not None:
        reasons.append(f"Model year {car['year']} is {filters.year_min} or newer")
    if filters.hp_min is not None and car.get("engine_hp") is not None:
        reasons.append(f"{car['engine_hp']} hp meets the {filters.hp_min} hp minimum")
    if filters.transmission_type and car.get("transmission_type"):
        reasons.append(f"Has the requested {car['transmission_type'].lower()} transmission")
    if filters.engine_fuel_type and car.get("engine_fuel_type"):
        reasons.append(f"Fuel type: {car['engine_fuel_type']}")
    if filters.makes:
        reasons.append(f"Make {car['make']} is one of the requested options")
    if filters.vehicle_styles and car.get("vehicle_style"):
        reasons.append(f"Requested body style: {car['vehicle_style']}")
    if filters.driven_wheels and car.get("driven_wheels"):
        reasons.append(f"Requested drivetrain: {car['driven_wheels']}")
    if filters.engine_cylinders_min is not None and car.get("engine_cylinders") is not None:
        reasons.append(
            f"{car['engine_cylinders']} cylinders meets the "
            f"{filters.engine_cylinders_min}-cylinder minimum"
        )
    if filters.combined_mpg_min is not None and car.get("combined_mpg") is not None:
        reasons.append(
            f"{car['combined_mpg']} combined MPG meets the "
            f"{filters.combined_mpg_min} MPG minimum"
        )
    if filters.highway_mpg_min is not None and car.get("highway_mpg") is not None:
        reasons.append(
            f"{car['highway_mpg']} highway MPG meets the "
            f"{filters.highway_mpg_min} MPG minimum"
        )
    if filters.q and car.get("vehicle_style"):
        reasons.append(f"Retrieved for preference match; body style is {car['vehicle_style']}")
    return reasons or ["Retrieved from the vehicle catalog for this request"]


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
