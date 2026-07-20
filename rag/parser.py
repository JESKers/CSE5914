"""Deterministic natural-language to structured vehicle-search filters."""
import json
import re
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from backend.app.schemas import SearchFilters

try:
    from search import search_service
except ImportError:  # pragma: no cover
    search_service = None


def _number(match) -> int:
    value = int(match.group(1).replace(",", ""))
    return value * (1000 if match.group(2) else 1)


def _extract_price_max(query: str):
    q = query.lower()
    patterns = [
        r"(?:under|below|less than)\s*\$?\s*([0-9]+(?:,[0-9]{3})?)(k)?",
        r"\$?\s*([0-9]+(?:,[0-9]{3})?)(k)?\s*(?:or less|and under)",
        r"(?:do not spend more than|maximum price of|my ceiling is)\s*\$?\s*([0-9]+(?:,[0-9]{3})?)(k)?",
        r"(?:car\s*)?<=\s*\$?\s*([0-9]+(?:,[0-9]{3})?)(k)?",
    ]
    for pattern in patterns:
        if match := re.search(pattern, q):
            suffix = q[match.end():].lstrip()
            if suffix.startswith("hp") or suffix.startswith("horsepower"):
                continue
            return _number(match)
    return None


def _extract_price_min(query: str):
    q = query.lower()
    if "do not spend more than" in q:
        return None
    match = re.search(r"(?:over|more than)\s*\$\s*([0-9]+(?:,[0-9]{3})?)(k)?", q)
    if not match:
        match = re.search(r"(?:over|more than)\s*([0-9]+(?:,[0-9]{3})?)(k)\b", q)
    return _number(match) + 1 if match else None


def _extract_years(query: str):
    q = query.lower()
    year = r"(?:20[0-9]{2}|19[0-9]{2})"
    if match := re.search(rf"(?:between|model years?)\s*({year})\s*(?:and|-)\s*({year})", q):
        return int(match.group(1)), int(match.group(2))

    year_min = year_max = None
    if match := re.search(rf"no older than\s*({year})", q):
        year_min = int(match.group(1))
    elif match := re.search(rf"({year})\s*or newer", q):
        year_min = int(match.group(1))
    elif match := re.search(rf"since\s*({year})", q):
        year_min = int(match.group(1))
    elif match := re.search(rf"(?:after|newer than)\s*({year})", q):
        year_min = int(match.group(1)) + 1

    if "no older than" not in q and (match := re.search(rf"(?:before|older than)\s*({year})", q)):
        year_max = int(match.group(1)) - 1
    exact = re.search(rf"\b({year})\b", q)
    if exact and year_min is None and year_max is None:
        year_min = year_max = int(exact.group(1))
    return year_min, year_max


def _extract_hp_range(query: str):
    q = query.lower()
    if match := re.search(r"between\s*([0-9]{2,4})\s*and\s*([0-9]{2,4})\s*(?:hp|horsepower)", q):
        return int(match.group(1)), int(match.group(2))
    if match := re.search(r"([0-9]{2,4})\s*(?:hp|horsepower)\s*exactly", q):
        value = int(match.group(1))
        return value, value
    return None, None


def _extract_hp_min(query: str):
    q = query.lower()
    patterns = [
        r"(?:at least|minimum|min\.?)\s*([0-9]{2,4})\s*(?:hp|horsepower)",
        r"([0-9]{2,4})\s*\+\s*(?:hp|horsepower)",
        r"(?:over|more than)\s*([0-9]{2,4})\s*(?:hp|horsepower)",
        r"(?:hp|horsepower)\s*>=\s*([0-9]{2,4})",
    ]
    for pattern in patterns:
        if match := re.search(pattern, q):
            value = int(match.group(1))
            return value + 1 if re.search(r"(?:over|more than)", match.group(0)) else value
    return None


def _extract_hp_max(query: str):
    q = query.lower()
    if match := re.search(r"(?:under|below|less than)\s*([0-9]{2,4})\s*(?:hp|horsepower)", q):
        return int(match.group(1)) - 1
    return None


BODY_STYLES = ["coupe", "suv", "sedan", "truck", "convertible", "wagon"]
MAKES = [
    "land rover", "mercedes-benz", "mercedes", "chevrolet", "chevy",
    "acura", "audi", "bmw", "buick", "cadillac", "chrysler", "dodge",
    "ford", "gmc", "honda", "hyundai", "infiniti", "jaguar", "jeep",
    "kia", "lexus", "lincoln", "mazda", "mini", "mitsubishi", "nissan",
    "porsche", "subaru", "tesla", "toyota", "volkswagen", "volvo",
]
MAKE_ALIASES = {
    "vw": "volkswagen", "volkswagon": "volkswagen",
    "bimmer": "bmw", "beemer": "bmw", "subie": "subaru",
    "caddy": "cadillac", "toyo": "toyota", "merc": "mercedes-benz",
    "benz": "mercedes-benz", "chevorlet": "chevrolet",
}


def _detect_make(q: str):
    found = []
    for token, canonical in [(make, make) for make in MAKES] + list(MAKE_ALIASES.items()):
        if not re.search(r"\b" + re.escape(token) + r"\b", q):
            continue
        if re.search(rf"\b(?:not|no)\s+(?:a\s+)?{re.escape(token)}\b", q):
            continue
        canonical = {"chevy": "chevrolet", "mercedes": "mercedes-benz"}.get(canonical, canonical)
        if canonical not in found:
            found.append(canonical)
    return found[0] if len(found) == 1 else None


@lru_cache(maxsize=64)
def _local_models(make: str) -> tuple[str, ...]:
    models = set()
    try:
        with (ROOT / "data" / "cars_clean.json").open(encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                if str(row.get("make", "")).casefold() == make.casefold() and row.get("model"):
                    models.add(str(row["model"]))
    except (OSError, ValueError):
        return ()
    return tuple(sorted(models, key=len, reverse=True))


def _detect_model(q: str, make):
    if not make:
        return None
    candidates = _local_models(make)
    if not candidates and search_service is not None:
        try:
            candidates = search_service.models(make)
        except Exception:
            return None
    normalized_query = re.sub(r"[^a-z0-9]+", " ", q).strip()
    best = None
    for model in candidates:
        normalized_model = re.sub(r"[^a-z0-9]+", " ", str(model).lower()).strip()
        if normalized_model and re.search(r"\b" + re.escape(normalized_model) + r"\b", normalized_query):
            if best is None or len(normalized_model) > len(best):
                best = str(model).lower()
    return best


def detect_intents(query: str) -> dict:
    q = query.lower()
    body_styles = [style for style in BODY_STYLES if style in q or f"{style}s" in q]
    transmission_choice = bool(re.search(r"manual\s+or\s+automatic|manual\s+automatic", q))
    make = _detect_make(q)
    return {
        "body_styles": body_styles,
        "sport": any(w in q for w in ["sporty", "sport", "fast", "performance", "powerful", "horsepower"]),
        "affordable": any(w in q for w in ["affordable", "cheap", "budget", "good price", "balance of price", "value"]),
        "fuel_efficient": any(w in q for w in ["fuel efficient", "fuel efficiency", "good mpg", "mpg", "commuting", "commuter", "daily"]),
        "luxury": any(w in q for w in ["luxury", "premium", "comfortable", "high end"]),
        "manual": bool(re.search(r"\b(?:manual|stick shift)\b", q)) and not transmission_choice and not re.search(r"\bnot\s+(?:a\s+)?manual\b", q),
        "automatic": bool(re.search(r"\bautomatic\b", q)) and not transmission_choice and not re.search(r"\bnot\s+(?:an?\s+)?automatic\b", q),
        "electric": (
            bool(re.search(r"\b(?:electric|ev)\b", q)) or make == "tesla"
        ) and not re.search(r"\b(?:not|no)\s+(?:an?\s+)?(?:electric|ev)\b", q),
        "hybrid": "hybrid" in q,
        "diesel": "diesel" in q and not re.search(r"\b(?:not|no)\s+diesel\b", q),
        "make": make,
        "model": _detect_model(q, make),
    }


def parse_query(query: str) -> SearchFilters:
    intents = detect_intents(query)
    filters = {"page": 1, "size": 20}
    keywords = []

    if value := _extract_price_max(query):
        filters["price_max"] = value
    if value := _extract_price_min(query):
        filters["price_min"] = value
    year_min, year_max = _extract_years(query)
    if year_min is not None:
        filters["year_min"] = year_min
    if year_max is not None:
        filters["year_max"] = year_max
    range_min, range_max = _extract_hp_range(query)
    hp_min = range_min or _extract_hp_min(query)
    hp_max = range_max or _extract_hp_max(query)
    if hp_min is not None:
        filters["hp_min"] = hp_min
    if hp_max is not None:
        filters["hp_max"] = hp_max

    for style in intents["body_styles"]:
        keywords.extend(["truck", "pickup"] if style == "truck" else [style])
    if intents["sport"]:
        keywords.extend(["sport", "performance"])
        filters.update(sort="hp", order="desc")
    if intents["affordable"]:
        keywords.extend(["affordable", "value"])
        if "sort" not in filters:
            filters.update(sort="price", order="asc")
        if "price_max" not in filters:
            filters["price_max"] = 30000 if intents["fuel_efficient"] else 50000
    if intents["fuel_efficient"]:
        keywords.extend(["fuel efficient", "mpg", "commuter"])
    if intents["luxury"]:
        keywords.extend(["luxury", "premium"])
    if intents["manual"]:
        filters["transmission_type"] = "MANUAL"
    if intents["automatic"]:
        filters["transmission_type"] = "AUTOMATIC"
    if intents["electric"]:
        filters["engine_fuel_type"] = "electric"
        keywords.append("electric")
    if intents["hybrid"]:
        keywords.append("hybrid")
    if intents["diesel"]:
        filters["engine_fuel_type"] = "diesel"
    if intents["make"]:
        filters["make"] = intents["make"]
    if intents["model"]:
        filters["model"] = intents["model"]
    filters["q"] = " ".join(dict.fromkeys(keywords)) if keywords else query
    return SearchFilters(**filters)
