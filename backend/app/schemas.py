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
    # Backward-compatible single-value fields used by the original API.
    make: Optional[str] = None
    model: Optional[str] = None
    engine_fuel_type: Optional[str] = None
    transmission_type: Optional[str] = None

    # OR-groups and exclusions used by natural-language recommendation queries.
    makes: Optional[list[str]] = None
    models: Optional[list[str]] = None
    excluded_makes: Optional[list[str]] = None
    excluded_models: Optional[list[str]] = None
    transmission_types: Optional[list[str]] = None
    excluded_transmission_types: Optional[list[str]] = None
    powertrains: Optional[list[str]] = None
    excluded_powertrains: Optional[list[str]] = None
    vehicle_styles: Optional[list[str]] = None
    preferred_vehicle_styles: Optional[list[str]] = None
    excluded_vehicle_styles: Optional[list[str]] = None
    vehicle_sizes: Optional[list[str]] = None
    preferred_vehicle_sizes: Optional[list[str]] = None
    driven_wheels: Optional[list[str]] = None
    preferred_driven_wheels: Optional[list[str]] = None
    excluded_driven_wheels: Optional[list[str]] = None
    market_categories: Optional[list[str]] = None
    preferred_market_categories: Optional[list[str]] = None
    excluded_market_categories: Optional[list[str]] = None

    # Numeric hard constraints supported by the committed catalog.
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    hp_min: Optional[int] = None
    hp_max: Optional[int] = None
    engine_cylinders_min: Optional[int] = None
    engine_cylinders_max: Optional[int] = None
    number_of_doors_min: Optional[int] = None
    number_of_doors_max: Optional[int] = None
    city_mpg_min: Optional[int] = None
    city_mpg_max: Optional[int] = None
    highway_mpg_min: Optional[int] = None
    highway_mpg_max: Optional[int] = None
    combined_mpg_min: Optional[int] = None
    combined_mpg_max: Optional[int] = None

    # Explicitly soft constraints affect ranking but never remove candidates.
    preferred_price_max: Optional[float] = None
    preferred_year_min: Optional[int] = None
    preferred_hp_min: Optional[int] = None
    preferred_combined_mpg_min: Optional[int] = None
    preferred_makes: Optional[list[str]] = None
    preferred_powertrains: Optional[list[str]] = None
    ranking_preferences: Optional[list[str]] = None

    # Requirements such as towing, safety features, listing mileage, or color
    # are retained for transparent warnings instead of being silently ignored.
    unsupported_preferences: Optional[list[str]] = None
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
    engine_cylinders: Optional[int] = None
    engine_fuel_type: Optional[str] = None
    transmission_type: Optional[str] = None
    driven_wheels: Optional[str] = None
    number_of_doors: Optional[int] = None
    market_category: Optional[str] = None
    vehicle_size: Optional[str] = None
    vehicle_style: Optional[str] = None
    highway_mpg: Optional[int] = None
    city_mpg: Optional[int] = None
    combined_mpg: Optional[int] = None


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
    query: str = Field(
        min_length=1,
        max_length=500,
        pattern=r".*\S.*",
        description="free-text request, e.g. 'fast sports car under $50,000'",
    )


class RecommendationResult(CarResult):
    """A retrieved car plus facts explaining why it matched the request."""
    match_reasons: list[str] = Field(default_factory=list)
    vpic_evidence: dict = Field(default_factory=dict)
    relaxed_constraints: list[str] = Field(default_factory=list)


class RecommendResponse(BaseModel):
    """Grounded recommendations; every result comes from Elasticsearch."""
    results: list[RecommendationResult]
    alternatives: list[RecommendationResult] = Field(default_factory=list)
    total: int
    query_echo: dict
    message: str
    narrative: str
    generation_mode: str
    sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommended_vehicle_ids: list[str] = Field(default_factory=list)
    comparison_points: list[str] = Field(default_factory=list)
    request_id: str
    timings_ms: dict[str, float] = Field(default_factory=dict)


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


class ChatRequest(BaseModel):
    """One user turn for the buy/rent assistant. Omit session_id to start fresh."""
    message: str = Field(min_length=1, description="the user's message")
    session_id: Optional[str] = None


class ChatToolEvent(BaseModel):
    """A tool the agent invoked this turn — rendered as activity in the chat UI."""
    tool: str
    summary: str
    is_error: bool = False


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    events: list[ChatToolEvent] = []


class AssistantBookingsResponse(BaseModel):
    """Everything the agent has booked — for demo verification."""
    rentals: list[dict] = []
    test_drives: list[dict] = []


class VpicDecodeResponse(BaseModel):
    vin: str
    summary: dict = Field(default_factory=dict)
    raw: dict = Field(default_factory=dict)


class VpicModelsResponse(BaseModel):
    make: str
    year: Optional[int] = None
    count: int = 0
    models: list[str] = []
