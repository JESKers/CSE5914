"""FastAPI entrypoint — wires the API contract to the search core + RAG parser.

Owner: Eric (Integration). Run from the repo root:
    uvicorn backend.app.main:app --reload

Endpoints (see docs/API_CONTRACT.md):
    GET  /health
    GET  /search     structured filters + keyword
    GET  /facets     dropdown buckets
    POST /recommend  free-text natural-language query (RAG spike)
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from search import search_service

from .config import settings
from .es_client import get_es
from .schemas import (
    CarResult,
    FacetsResponse,
    ModelsResponse,
    RecommendRequest,
    RecommendResponse,
    SearchFilters,
    SearchResponse,
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
    from rag.parser import parse_query  # lazy import: only /recommend needs the local parser

    filters = parse_query(req.query)
    res = search_service.search(filters)
    return RecommendResponse(
        results=_to_results(res["results"]),
        total=res["total"],
        query_echo={"query": req.query, "parsed_filters": filters.model_dump(exclude_none=True)},
    )
