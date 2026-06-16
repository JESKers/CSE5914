"""API contract — request filters and response models.

Owned by Eric (Integration). This is the shared schema all roles code against:
- Kangjie's search_service maps SearchFilters -> ES query and returns SearchResponse.
- Jerry's nl_search produces SearchFilters from natural language.
- Shangrui's frontend sends these query params and renders CarResult.
Freeze this on Day 1; changes here ripple to everyone.
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
    total: int
    page: int
    size: int
    results: list[CarResult]


class FacetBucket(BaseModel):
    key: str
    count: int


class FacetsResponse(BaseModel):
    makes: list[FacetBucket] = []
    transmissions: list[FacetBucket] = []
    fuel_types: list[FacetBucket] = []


class NLSearchRequest(BaseModel):
    query: str


class NLSearchResponse(BaseModel):
    parsed_filters: SearchFilters
    results: list[CarResult]
