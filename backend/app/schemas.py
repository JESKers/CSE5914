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
    years: list[int] = []  # distinct years (desc) for the year-range dropdowns


class ModelsResponse(BaseModel):
    """Models available for a given make — drives the dependent Model dropdown."""
    make: str
    models: list[str] = []


class RecommendRequest(BaseModel):
    query: str = Field(description="free-text request, e.g. 'fast sports car under $50,000'")


class RecommendResponse(BaseModel):
    """Same envelope as /search; query_echo carries the parsed filters."""
    results: list[CarResult]
    total: int
    query_echo: dict


# --------------------------------------------------------------------------- #
# Buy / Rent store — additive feature (see docs/STORE_VPIC.md). These extend,
# but do not modify, the frozen /search + /recommend contract above.
# --------------------------------------------------------------------------- #
class ListingResult(CarResult):
    """A catalog car priced and stocked for purchase or rental."""
    buy_price: float = 0.0
    rent_daily: float = 0.0
    seats: Optional[int] = None
    for_rent: bool = False
    stock: int = 0
    vpic_verified: bool = False  # make exists in the NHTSA vPIC directory


class ListingsResponse(BaseModel):
    """Envelope mirroring /search, for store listings."""
    results: list[ListingResult]
    total: int
    mode: str = "buy"           # "buy" | "rent"
    query_echo: dict = Field(default_factory=dict)
    page: int = 1
    size: int = 20


class OrderRequest(BaseModel):
    vehicle_id: str
    mode: str = Field(description="'buy' or 'rent'")
    rent_days: Optional[int] = Field(default=None, ge=1, le=365)
    customer: Optional[str] = None


class OrderResponse(BaseModel):
    order_id: int
    vehicle: str
    mode: str
    rent_days: Optional[int] = None
    total: float
    status: str = "confirmed"
    message: str


class Order(BaseModel):
    id: int
    vehicle_id: str
    label: str
    mode: str
    rent_days: Optional[int] = None
    total: float
    customer: Optional[str] = None
    created_at: str


class OrdersResponse(BaseModel):
    orders: list[Order] = []


class VpicDecodeResponse(BaseModel):
    vin: str
    summary: dict = Field(default_factory=dict)
    raw: dict = Field(default_factory=dict)


class VpicModelsResponse(BaseModel):
    make: str
    year: Optional[int] = None
    count: int = 0
    models: list[str] = []
