"""Natural-language -> structured filters (Timebox 3 spike).

Uses a local Ollama chat model so the rag package can run without an API key.
"""
import json
import sys
from pathlib import Path

from langchain_core.messages import HumanMessage

try:
    from .ollama_utils import get_chat_model
except ImportError:  # pragma: no cover - allows direct script execution
    from ollama_utils import get_chat_model

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

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
    """Ask the local Ollama model for structured filters and validate the schema."""
    llm = get_chat_model(temperature=0.0)
    response = llm.invoke([HumanMessage(content=f"{_SYSTEM}\n\nUser query: {query}")])
    raw = response.content if hasattr(response, "content") else str(response)
    raw = raw.strip()
    if raw.startswith("```"):  # tolerate fenced code blocks
        raw = raw.split("```")[1].lstrip("json").strip()
    data = json.loads(raw)
    return SearchFilters(**data)  # pydantic ignores unknown keys, validates types
