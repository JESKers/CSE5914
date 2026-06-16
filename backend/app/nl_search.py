"""Natural-language -> structured filters (Timebox 3 spike).

Owner: Jerry. Uses an LLM to turn a phrase like
"fast sports car under $50,000" into SearchFilters, which are then handed to
search_service.search(). This is the de-risking prototype for the RAG/LLM
deliverable in Timebox 3 — keep it behind the /nl-search endpoint.
"""
import json

from anthropic import Anthropic

from .config import settings
from .schemas import NLSearchResponse, SearchFilters
from .search_service import search

_SYSTEM = """You translate a shopper's car request into JSON search filters.
Return ONLY a JSON object with any of these optional keys:
make, model, year_min, year_max, price_min, price_max, hp_min, hp_max,
engine_fuel_type, transmission_type, q (free-text keywords), sort, order.
Example: "fast sports car under $50,000" ->
{"vehicle_style style hints go in q": ...}  (use q for fuzzy descriptors).
Numbers only for numeric fields. Omit keys you cannot infer."""


def parse_query(query: str) -> SearchFilters:
    """Ask the LLM for structured filters; validate against the schema."""
    client = Anthropic(api_key=settings.anthropic_api_key)
    resp = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=512,
        system=_SYSTEM,
        messages=[{"role": "user", "content": query}],
    )
    raw = resp.content[0].text.strip()
    # tolerate fenced code blocks
    if raw.startswith("```"):
        raw = raw.split("```")[1].lstrip("json").strip()
    data = json.loads(raw)
    return SearchFilters(**data)  # pydantic ignores unknown keys, validates types


def nl_search(query: str) -> NLSearchResponse:
    filters = parse_query(query)
    results = search(filters)
    return NLSearchResponse(parsed_filters=filters, results=results.results)
