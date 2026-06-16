"""API contract — request filters and response models.

Owned by Eric (Integration). The shared schema all roles code against:
- search.search_service maps SearchFilters -> ES query, returns dicts.
- rag.parser produces SearchFilters from natural language.
- the frontend sends these query params and renders CarResult.
See docs/API_CONTRACT.md. Freeze this on Day 1.
"""
from typing import Optional

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    hp_min: Optional[int] = None
    hp_max: Optional[int] = None
    engine_fuel_type: Optional[str] = None
    transmission_type: Optional[str] = None
    q: Optional[str] = Field(default=None, description="free-text keywords")

    # paging / sorting
    sort: str = Field(default="popularity", description="price|year|hp|popularity")
    order: str = Field(default="desc", description="asc|desc")
    page: int = 1
    size: int = 20


class CarResult(BaseModel):
    id: str
    make: str
    model: str
    year: Optional[int] = None
    msrp: Optional[float] = None
    engine_hp: Optional[int] = None
    engine_fuel_type: Optional[str] = None
    transmission_type: Optional[str] = None
    vehicle_style: Optional[str] = None
    highway_mpg: Optional[int] = None
    city_mpg: Optional[int] = None


class SearchResponse(BaseModel):
    """Shared response envelope: { results, total, query_echo }."""
    results: list[CarResult]
    total: int
    query_echo: dict = Field(default_factory=dict, description="echo of the filters/query applied")
    page: int = 1
    size: int = 20


class FacetBucket(BaseModel):
    key: str
    count: int


class FacetsResponse(BaseModel):
    makes: list[FacetBucket] = []
    transmissions: list[FacetBucket] = []
    fuel_types: list[FacetBucket] = []


class RecommendRequest(BaseModel):
    query: str = Field(description="free-text request, e.g. 'fast sports car under $50,000'")


class RecommendResponse(BaseModel):
    """Same envelope as /search; query_echo carries the parsed filters."""
    results: list[CarResult]
    total: int
    query_echo: dict
