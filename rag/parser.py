"""Natural-language -> structured filters (Timebox 3 spike).

Owner: Jerry. Turns "fast sports car under $50,000" into SearchFilters, which
the backend hands to search.search_service.search(). The de-risking prototype
for the RAG/LLM recommendation deliverable — exercised via POST /recommend.

Evaluated against rag/test_queries.md.
"""
import json

from anthropic import Anthropic

from backend.app.config import settings
from backend.app.schemas import SearchFilters

_SYSTEM = """You translate a car shopper's request into JSON search filters.
Return ONLY a JSON object using any of these optional keys:
  make, model, year_min, year_max, price_min, price_max, hp_min, hp_max,
  engine_fuel_type, transmission_type, q, sort, order
Rules:
- Numeric fields take numbers only (e.g. "under $50,000" -> price_max: 50000).
- Put fuzzy descriptors (sporty, luxury, coupe, SUV) into `q` as keywords.
- "fast"/"powerful" -> sort: "hp", order: "desc"; "cheap" -> sort: "price", order: "asc".
- Omit any key you cannot confidently infer."""


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
    if raw.startswith("```"):  # tolerate fenced code blocks
        raw = raw.split("```")[1].lstrip("json").strip()
    data = json.loads(raw)
    return SearchFilters(**data)  # pydantic ignores unknown keys, validates types
