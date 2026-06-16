"""FastAPI entrypoint — wires the API contract to the search core.

Owner: Eric (Integration).
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .es_client import get_es
from .schemas import (
    FacetsResponse,
    NLSearchRequest,
    NLSearchResponse,
    SearchFilters,
    SearchResponse,
)
from . import search_service

app = FastAPI(title="JESKers Car Search", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    return search_service.search(filters)


@app.get("/facets", response_model=FacetsResponse)
def facets():
    return search_service.facets()


@app.post("/nl-search", response_model=NLSearchResponse)
def nl_search(req: NLSearchRequest):
    """Experimental — Jerry's NL spike (Timebox 3 prep)."""
    if not settings.anthropic_api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY not configured")
    from .nl_search import nl_search as run_nl_search

    return run_nl_search(req.query)
