"""Natural-language -> structured filters.

This version keeps parsing deterministic for the demo.
It avoids relying completely on the LLM because bad filter parsing causes bad RAG context.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from backend.app.schemas import SearchFilters

try:
    from search import search_service
except ImportError:  # pragma: no cover - search core unavailable in some contexts
    search_service = None


def _extract_price_max(query: str):
    q = query.lower()

    # Match phrases like "under $50,000", "below 30000", "less than 25k"
    patterns = [
        r"(?:under|below|less than)\s*\$?\s*([0-9]+(?:,[0-9]{3})?)(k)?",
        r"\$?\s*([0-9]+(?:,[0-9]{3})?)(k)?\s*(?:or less|and under)",
    ]

    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            value = match.group(1).replace(",", "")
            number = int(value)

            if match.group(2) == "k":
                number *= 1000

            return number

    return None


def _extract_years(query: str):
    q = query.lower()

    year_min = None
    year_max = None

    after_match = re.search(r"(?:after|newer than|since)\s*(20[0-9]{2}|19[0-9]{2})", q)
    before_match = re.search(r"(?:before|older than)\s*(20[0-9]{2}|19[0-9]{2})", q)
    exact_match = re.search(r"\b(20[0-9]{2}|19[0-9]{2})\b", q)

    if after_match:
        year_min = int(after_match.group(1))

    if before_match:
        year_max = int(before_match.group(1))

    if exact_match and not year_min and not year_max:
        year_min = int(exact_match.group(1))
        year_max = int(exact_match.group(1))

    return year_min, year_max


# Ordered so the first matching style wins when a query mentions more than one
# (mirrors how a human would prioritize the most specific body-style word).
BODY_STYLES = ["coupe", "suv", "sedan", "truck", "convertible", "wagon"]

MAKES = [
    "land rover",
    "mercedes-benz",
    "mercedes",
    "chevrolet",
    "chevy",
    "acura",
    "audi",
    "bmw",
    "buick",
    "cadillac",
    "chrysler",
    "dodge",
    "ford",
    "gmc",
    "honda",
    "hyundai",
    "infiniti",
    "jaguar",
    "jeep",
    "kia",
    "lexus",
    "lincoln",
    "mazda",
    "mini",
    "mitsubishi",
    "nissan",
    "porsche",
    "subaru",
    "tesla",
    "toyota",
    "volkswagen",
    "volvo",
]


def _detect_make(q: str):
    # Returned value must match the casing actually indexed in Elasticsearch
    # (lowercase `keyword` field) since search_service uses an exact `term`
    # filter on `make` -- any mismatch here silently drops every result.
    for make in MAKES:
        if re.search(r"\b" + re.escape(make) + r"\b", q):
            if make == "chevy":
                return "chevrolet"
            if make == "mercedes":
                return "mercedes-benz"
            return make
    return None


def _detect_model(q: str, make):
    """Match a known model name for `make` against the query text.

    Looks up the live list of models for the detected make (same facet the
    frontend's dependent Model dropdown uses) instead of maintaining a giant
    static model list, so it stays correct as the dataset changes.
    """
    if not make or search_service is None:
        return None

    try:
        candidates = search_service.models(make)
    except Exception:
        return None

    best = None
    for model in candidates:
        model_l = str(model).lower()
        if model_l and re.search(r"\b" + re.escape(model_l) + r"\b", q):
            if best is None or len(model_l) > len(best):
                best = model_l
    return best


def detect_intents(query: str) -> dict:
    """Single source of truth for keyword/intent detection.

    Both `parse_query` (filters) and `rag.recommend` (extra-query fan-out +
    re-ranking) call this instead of independently re-matching the same
    keywords, so adding/adjusting an intent only needs to happen here.
    """
    q = query.lower()

    body_styles = [style for style in BODY_STYLES if style in q or f"{style}s" in q]

    return {
        "body_styles": body_styles,
        "sport": any(
            w in q for w in ["sporty", "sport", "fast", "performance", "powerful", "horsepower"]
        ),
        "affordable": any(
            w in q
            for w in ["affordable", "cheap", "budget", "good price", "balance of price", "value"]
        ),
        "fuel_efficient": any(
            w in q
            for w in [
                "fuel efficient", "fuel efficiency", "good mpg", "mpg",
                "commuting", "commuter", "daily",
            ]
        ),
        "luxury": any(w in q for w in ["luxury", "premium", "comfortable", "high end"]),
        "manual": "manual" in q,
        "automatic": "automatic" in q,
        "electric": "electric" in q or "ev" in q,
        "hybrid": "hybrid" in q,
        "diesel": "diesel" in q,
        "make": (make := _detect_make(q)),
        "model": _detect_model(q, make),
    }


def parse_query(query: str) -> SearchFilters:
    intents = detect_intents(query)

    filters = {
        "page": 1,
        "size": 20,
    }

    keywords = []

    price_max = _extract_price_max(query)
    if price_max:
        filters["price_max"] = price_max

    year_min, year_max = _extract_years(query)
    if year_min:
        filters["year_min"] = year_min
    if year_max:
        filters["year_max"] = year_max

    # Body/style intent
    for style in intents["body_styles"]:
        if style == "truck":
            keywords.extend(["truck", "pickup"])
        else:
            keywords.append(style)

    # Performance intent
    if intents["sport"]:
        keywords.extend(["sport", "performance"])
        filters["sort"] = "hp"
        filters["order"] = "desc"

    # Affordable/value intent
    if intents["affordable"]:
        keywords.extend(["affordable", "value"])

        if "sort" not in filters:
            filters["sort"] = "price"
            filters["order"] = "asc"

        if "price_max" not in filters:
            filters["price_max"] = 50000

    # Fuel efficiency / commuting intent
    if intents["fuel_efficient"]:
        keywords.extend(["fuel efficient", "mpg", "commuter"])
        if "price_max" not in filters and intents["affordable"]:
            filters["price_max"] = 30000

    # Luxury intent
    if intents["luxury"]:
        keywords.extend(["luxury", "premium"])

    # Transmission intent
    if intents["manual"]:
        filters["transmission_type"] = "MANUAL"

    if intents["automatic"]:
        filters["transmission_type"] = "AUTOMATIC"

    # Fuel type intent
    if intents["electric"]:
        filters["engine_fuel_type"] = "electric"
        keywords.append("electric")

    if intents["hybrid"]:
        keywords.append("hybrid")

    if intents["diesel"]:
        filters["engine_fuel_type"] = "diesel"

    # Brand detection
    if intents["make"]:
        filters["make"] = intents["make"]

    # Model detection (only meaningful once the make narrows the candidate list)
    if intents["model"]:
        filters["model"] = intents["model"]

    # Final q string
    if keywords:
        filters["q"] = " ".join(dict.fromkeys(keywords))
    else:
        filters["q"] = query

    return SearchFilters(**filters)