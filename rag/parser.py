"""Data-aware natural-language planning for vehicle search.

The parser deliberately separates:
- hard constraints that Elasticsearch can enforce,
- soft preferences that only influence ranking, and
- requirements the committed catalog cannot verify.

This keeps complex, conversational requests useful without pretending the
dataset contains safety, reliability, towing, listing-mileage, or feature data.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
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


YEAR = r"(?:19[0-9]{2}|20[0-9]{2})"
NUMBER = r"[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?"
SOFT_CUES = re.compile(
    r"(?:prefer(?:ably)?|ideally|would like|nice to have|bonus(?: points)?|"
    r"if possible|not required|don'?t need|optional|would be nice|target)",
)
NEGATIVE_CUES = re.compile(
    r"(?:\bno\b|\bnot\b|\bwithout\b|\bavoid\b|\bexclude\b|\bexcept\b|"
    r"anything but|nothing(?:\s+too)?|do not want|don'?t want|won'?t consider|must not)",
)

MAKES = [
    "alfa romeo", "aston martin", "land rover", "mercedes-benz", "mercedes",
    "chevrolet", "chevy", "acura", "audi", "bentley", "bmw", "bugatti",
    "buick", "cadillac", "chrysler", "dodge", "ferrari", "fiat", "ford",
    "genesis", "gmc", "honda", "hummer", "hyundai", "infiniti", "jaguar",
    "jeep", "kia", "lamborghini", "lexus", "lincoln", "lotus", "maserati",
    "mazda", "mclaren", "mini", "mitsubishi", "nissan", "porsche", "ram",
    "rolls-royce", "saab", "scion", "smart", "subaru", "suzuki", "tesla",
    "toyota", "volkswagen", "volvo",
]
MAKE_ALIASES = {
    "vw": "volkswagen",
    "volkswagon": "volkswagen",
    "bimmer": "bmw",
    "beemer": "bmw",
    "subie": "subaru",
    "caddy": "cadillac",
    "toyo": "toyota",
    "merc": "mercedes-benz",
    "benz": "mercedes-benz",
    "chevorlet": "chevrolet",
    "vette": "chevrolet",
    "lambo": "lamborghini",
}
CANONICAL_MAKES = {
    "chevy": "chevrolet",
    "mercedes": "mercedes-benz",
    **MAKE_ALIASES,
}

STYLE_PATTERNS = [
    (r"\bconvertible\s+suvs?\b", ["Convertible SUV"]),
    (r"\b(?:pickup\s+trucks?|pickups?|trucks?)\b",
     ["Crew Cab Pickup", "Extended Cab Pickup", "Regular Cab Pickup"]),
    (r"\b(?:minivans?|people\s+movers?)\b", ["Passenger Minivan", "Cargo Minivan"]),
    (r"\b(?:cargo\s+vans?)\b", ["Cargo Van", "Cargo Minivan"]),
    (r"\b(?:passenger\s+vans?|vans?)\b", ["Passenger Van", "Cargo Van"]),
    (r"\b(?:suvs?|crossovers?|sport\s+utility\s+vehicles?)\b",
     ["4dr SUV", "2dr SUV", "Convertible SUV"]),
    (r"\b(?:hatchbacks?|hatch(?:es)?)\b", ["4dr Hatchback", "2dr Hatchback"]),
    (r"\b(?:station\s+wagons?|wagons?|estates?)\b", ["Wagon"]),
    (r"\b(?:convertibles?|cabriolets?|roadsters?)\b", ["Convertible"]),
    (r"\b(?:coupes?|two[- ]door\s+sports?\s+cars?)\b", ["Coupe"]),
    (r"\b(?:sedans?|saloons?)\b", ["Sedan"]),
]
SIZE_PATTERNS = [
    (r"\b(?:subcompact|small|compact)\b", "Compact"),
    (r"\b(?:mid[- ]?size|midsize|medium[- ]size)\b", "Midsize"),
    (r"\b(?:full[- ]size|large)\b", "Large"),
]
DRIVETRAIN_PATTERNS = [
    (r"\b(?:all[- ]wheel[- ]drive|awd)\b", "all wheel drive"),
    (r"\b(?:four[- ]wheel[- ]drive|4wd|4x4)\b", "four wheel drive"),
    (r"\b(?:front[- ]wheel[- ]drive|fwd)\b", "front wheel drive"),
    (r"\b(?:rear[- ]wheel[- ]drive|rwd)\b", "rear wheel drive"),
]
TRANSMISSION_PATTERNS = [
    (r"\b(?:automated[- ]manual|dual[- ]clutch|dct)\b", "AUTOMATED_MANUAL"),
    (r"\b(?:direct[- ]drive)\b", "DIRECT_DRIVE"),
    (r"\b(?:stick(?:\s+shift)?|manual)\b", "MANUAL"),
    (r"\b(?:automatics?|auto)\b", "AUTOMATIC"),
]
POWERTRAIN_PATTERNS = [
    (r"\b(?:battery[- ]electric|electric|ev)\b", "electric"),
    (r"\b(?:plug[- ]in\s+hybrid|phev|hybrid)\b", "hybrid"),
    (r"\b(?:diesel)\b", "diesel"),
    (r"\b(?:flex[- ]?fuel|e85)\b", "flex-fuel"),
    (r"\b(?:gasoline|petrol|gas[- ]powered)\b", "gasoline"),
    (r"\b(?:natural\s+gas|cng)\b", "natural gas"),
]


def _normalize(query: str) -> str:
    return (
        query.casefold()
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
        .replace("\u00a0", " ")
    )


def _unique(values) -> list:
    return list(dict.fromkeys(value for value in values if value is not None))


def _context_mode(q: str, start: int) -> str:
    """Classify one mention as hard, preferred, or excluded from nearby cues."""
    prefix = q[max(0, start - 70):start]
    local = re.split(r"[.,;!?]", prefix)[-1]
    suffix = q[start:start + 60]
    if NEGATIVE_CUES.search(local):
        return "excluded"
    if SOFT_CUES.search(local) or re.match(
        r"[^,.;!?]{0,25}\b(?:preferred|optional|not required|would be nice|if possible)\b",
        suffix,
    ):
        return "preferred"
    return "hard"


def _money_value(match: re.Match, name: str) -> int:
    raw = match.group(name).replace(",", "")
    value = float(raw)
    suffix = (match.groupdict().get(f"{name}_suffix") or "").casefold()
    if suffix in {"k", "grand", "thousand"}:
        value *= 1000
    return int(round(value))


def _money(name: str) -> str:
    return (
        rf"(?P<{name}>{NUMBER})\s*"
        rf"(?P<{name}_suffix>k|grand|thousand)?"
    )


def _plausible_price(value: int) -> bool:
    return 1000 <= value <= 10_000_000


def _extract_prices(q: str) -> dict:
    result: dict = {}
    if re.search(r"\b(?:monthly|per month|a month|/mo|payment)\b", q):
        # Avoid treating a monthly payment as MSRP; the limitation detector
        # retains it for a transparent warning.
        monthly_spans = [m.span() for m in re.finditer(
            r".{0,25}\b(?:monthly|per month|a month|/mo|payment)\b.{0,25}", q
        )]
    else:
        monthly_spans = []

    def in_monthly_span(match: re.Match) -> bool:
        return any(start <= match.start() <= end for start, end in monthly_spans)

    # "35k, but I can stretch to 40k" expresses a preferred and an absolute cap.
    stretch = re.search(
        rf"(?:budget(?:\s+is|\s+of)?|stay\s+(?:under|below)|prefer(?:ably)?\s+(?:under|below))"
        rf"\s*\$?\s*{_money('preferred')}.{{0,80}}?"
        rf"(?:stretch|go|absolute\s+max(?:imum)?|up\s+to).{{0,15}}?"
        rf"\$?\s*{_money('absolute')}",
        q,
    )
    if stretch:
        preferred = _money_value(stretch, "preferred")
        absolute = _money_value(stretch, "absolute")
        if _plausible_price(preferred) and _plausible_price(absolute):
            result["preferred_price_max"] = preferred
            result["price_max"] = max(preferred, absolute)
            return result

    # Explicit price bands, including shorthand such as "$20-30k".
    for pattern in (
        rf"(?:between|from|range(?:\s+is|\s+of)?)\s*\$?\s*{_money('low')}"
        rf"\s*(?:and|to|-)\s*\$?\s*{_money('high')}",
        rf"\$?\s*{_money('low')}\s*-\s*\$?\s*{_money('high')}"
        rf"\s*(?:budget|price|range|cars?)?\b",
    ):
        match = re.search(pattern, q)
        if not match or in_monthly_span(match):
            continue
        low = _money_value(match, "low")
        high = _money_value(match, "high")
        # In "$20-30k", the final suffix applies to both numbers.
        if not match.groupdict().get("low_suffix") and match.groupdict().get("high_suffix"):
            low *= 1000
        if _plausible_price(low) and _plausible_price(high):
            if 1900 <= low <= 2099 and 1900 <= high <= 2099:
                continue
            result["price_min"], result["price_max"] = sorted((low, high))
            return result

    # Colloquial bands: "low 20s", "mid-30s", "high 40s".
    if match := re.search(r"\b(low|mid|high)[- ]?\$?([1-9][0-9])s\b", q):
        base = int(match.group(2)) * 1000
        offsets = {"low": (0, 5000), "mid": (3000, 7000), "high": (7000, 10000)}
        low_offset, high_offset = offsets[match.group(1)]
        result.update(price_min=base + low_offset, price_max=base + high_offset)
        return result

    max_patterns = [
        rf"(?:under|below|less\s+than|up\s+to|at\s+most|no\s+more\s+than)"
        rf"\s*\$?\s*{_money('value')}",
        rf"\$?\s*{_money('value')}\s*(?:or\s+less|and\s+under|max(?:imum)?|cap)\b",
        rf"(?:do\s+not\s+spend\s+more\s+than|not\s+exceed|maximum\s+price(?:\s+of)?|"
        rf"max\s+budget(?:\s+of)?|price\s+limit(?:\s+of)?|ceiling\s+is)"
        rf"\s*\$?\s*{_money('value')}",
        rf"(?:budget(?:\s+is|\s+of)?|have)\s*\$?\s*{_money('value')}"
        rf"\s*(?:to\s+spend)?\b",
        rf"(?:car\s*)?<=\s*\$?\s*{_money('value')}",
    ]
    for pattern in max_patterns:
        match = re.search(pattern, q)
        if not match or in_monthly_span(match):
            continue
        value = _money_value(match, "value")
        suffix = q[match.end():].lstrip()
        if suffix.startswith(("hp", "horsepower", "mpg", "mile")) or not _plausible_price(value):
            continue
        if _context_mode(q, match.start()) == "preferred":
            result["preferred_price_max"] = value
        else:
            result["price_max"] = value
        break

    min_patterns = [
        rf"(?:at\s+least|minimum(?:\s+price)?(?:\s+of)?|over|more\s+than)"
        rf"\s*\$\s*{_money('value')}",
        rf"(?:over|more\s+than)\s*{_money('value')}\b",
    ]
    for pattern in min_patterns:
        match = re.search(pattern, q)
        if not match or in_monthly_span(match):
            continue
        if re.search(
            r"(?:do not spend|no)\s+more\s+than",
            q[max(0, match.start() - 20):match.end()],
        ):
            continue
        value = _money_value(match, "value")
        suffix = q[match.end():].lstrip()
        if suffix.startswith(("hp", "horsepower", "mpg", "mile")):
            continue
        if not _plausible_price(value):
            continue
        result["price_min"] = value + (
            1 if re.match(r"(?:over|more\s+than)", match.group(0).lstrip("$ ")) else 0
        )
        break

    # "Around/about 30k" is a ranking target, not a fabricated hard range.
    if "preferred_price_max" not in result:
        match = re.search(
            rf"(?:around|about|roughly|approximately|target(?:\s+budget)?(?:\s+is)?)"
            rf"\s*\$?\s*{_money('value')}",
            q,
        )
        if match:
            value = _money_value(match, "value")
            if _plausible_price(value):
                result["preferred_price_max"] = value
    return result


@lru_cache(maxsize=1)
def _catalog_year_bounds() -> tuple[int, int]:
    years = []
    try:
        with (ROOT / "data" / "cars_clean.json").open(encoding="utf-8") as fh:
            for line in fh:
                year = json.loads(line).get("year")
                if isinstance(year, int):
                    years.append(year)
    except (OSError, ValueError):
        return 1990, 2020
    return (min(years), max(years)) if years else (1990, 2020)


def _extract_years(q: str) -> dict:
    result: dict = {}
    if match := re.search(
        rf"(?:between|model\s+years?|from)?\s*({YEAR})\s*"
        rf"(?:and|to|through|-)\s*({YEAR})",
        q,
    ):
        result["year_min"], result["year_max"] = sorted(
            (int(match.group(1)), int(match.group(2)))
        )
        return result
    if match := re.search(rf"\b({YEAR})\s*-\s*({YEAR})\b", q):
        result["year_min"], result["year_max"] = sorted(
            (int(match.group(1)), int(match.group(2)))
        )
        return result
    relative_years = {
        "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }
    if match := re.search(
        r"\b(?:last|past)\s+([1-9]|10|two|three|four|five|six|seven|eight|nine|ten)"
        r"\s+(?:model\s+)?years?\b",
        q,
    ):
        _, maximum = _catalog_year_bounds()
        token = match.group(1)
        count = int(token) if token.isdigit() else relative_years[token]
        result.update(year_min=maximum - count + 1, year_max=maximum)
        return result

    # Vehicle age is relative to today, unlike "last N model years", which is
    # explicitly relative to the committed catalog's available model years.
    if match := re.search(
        r"\b(?:at most|up to|no more than|maximum(?: of)?)\s+"
        r"([1-9]|10)\s+years?\s+old\b",
        q,
    ):
        age = int(match.group(1))
        result.update(year_min=date.today().year - age, year_max=date.today().year)
        return result
    if match := re.search(r"\b([1-9]|10)[- ]years?[- ]old\b", q):
        model_year = date.today().year - int(match.group(1))
        result.update(year_min=model_year, year_max=model_year)
        return result

    candidates = [
        (rf"no\s+older\s+than\s*({YEAR})", "year_min", 0),
        (rf"({YEAR})\s*\+", "year_min", 0),
        (rf"({YEAR})\s*or\s+newer", "year_min", 0),
        (rf"(?:since|from)\s*({YEAR})", "year_min", 0),
        (rf"(?:after|newer\s+than)\s*({YEAR})", "year_min", 1),
        (rf"({YEAR})\s*or\s+older", "year_max", 0),
        (rf"(?:before|older\s+than)\s*({YEAR})", "year_max", -1),
    ]
    for pattern, field, offset in candidates:
        for match in re.finditer(pattern, q):
            if field == "year_max" and "no older than" in q[max(0, match.start() - 5):match.end()]:
                continue
            value = int(match.group(1)) + offset
            target = field
            if field == "year_min" and _context_mode(q, match.start()) == "preferred":
                target = "preferred_year_min"
            result[target] = value

    years = [int(value) for value in re.findall(rf"\b({YEAR})\b", q)]
    if not result and len(years) == 1:
        result["year_min"] = result["year_max"] = years[0]
    # Preserve the original suite's interpretation of a bare "from 2020".
    if re.fullmatch(rf"\s*from\s+({YEAR})\s*", q):
        result["year_min"] = result["year_max"] = years[0]
    return result


def _extract_labeled_range(
    q: str,
    unit: str,
    minimum_field: str,
    maximum_field: str,
    *,
    value_digits: str = r"[0-9]{1,4}",
) -> dict:
    result = {}
    unit_pattern = rf"(?:{unit})"
    if match := re.search(
        rf"(?:between|from)\s*({value_digits})\s*(?:and|to|-)\s*"
        rf"({value_digits})\s*{unit_pattern}",
        q,
    ):
        result[minimum_field], result[maximum_field] = sorted(
            (int(match.group(1)), int(match.group(2)))
        )
        return result
    if match := re.search(
        rf"({value_digits})\s*-\s*({value_digits})\s*{unit_pattern}", q
    ):
        result[minimum_field], result[maximum_field] = sorted(
            (int(match.group(1)), int(match.group(2)))
        )
        return result

    minimum_patterns = [
        rf"(?:at\s+least|minimum|min\.?)\s*({value_digits})\s*{unit_pattern}",
        rf"({value_digits})\s*\+\s*{unit_pattern}",
        rf"(?:over|more\s+than|better\s+than)\s*({value_digits})\s*{unit_pattern}",
        rf"{unit_pattern}\s*>=\s*({value_digits})",
    ]
    for pattern in minimum_patterns:
        if match := re.search(pattern, q):
            if re.search(
                r"\bno\s+more\s+than\b",
                q[max(0, match.start() - 5):match.end()],
            ):
                continue
            value = int(match.group(1))
            if re.search(r"(?:over|more\s+than|better\s+than)", match.group(0)):
                value += 1
            result[minimum_field] = value
            break
    maximum_patterns = [
        rf"(?:under|below|less\s+than)\s*({value_digits})\s*{unit_pattern}",
        rf"(?:at\s+most|no\s+more\s+than|up\s+to)\s*({value_digits})\s*{unit_pattern}",
    ]
    for pattern in maximum_patterns:
        if match := re.search(pattern, q):
            value = int(match.group(1))
            if re.search(r"(?:under|below|less\s+than)", match.group(0)):
                value -= 1
            result[maximum_field] = value
            break
    if match := re.search(rf"({value_digits})\s*{unit_pattern}\s*exactly", q):
        value = int(match.group(1))
        result[minimum_field] = result[maximum_field] = value
    if match := re.search(rf"exactly\s*({value_digits})\s*{unit_pattern}", q):
        value = int(match.group(1))
        result[minimum_field] = result[maximum_field] = value
    return result


def _extract_horsepower(q: str) -> dict:
    result = _extract_labeled_range(
        q, r"hp|horsepower", "hp_min", "hp_max", value_digits=r"[0-9]{2,4}"
    )
    if not result and (match := re.search(r"\b([0-9]{2,4})\s*(?:hp|horsepower)\b", q)):
        if "at least" in q[max(0, match.start() - 45):match.start()]:
            result["hp_min"] = int(match.group(1))
    for field in ("hp_min",):
        if field in result:
            match = re.search(r"(?:hp|horsepower)", q)
            if match and _context_mode(q, match.start()) == "preferred":
                result["preferred_hp_min"] = result.pop(field)
    return result


def _extract_mpg(q: str) -> dict:
    result = {}
    unit_match = re.search(r"\b(?:mpg|miles\s+per\s+gallon)\b", q)
    if not unit_match:
        return result
    scope = "combined"
    prefix = q[max(0, unit_match.start() - 35):unit_match.start()]
    if "highway" in prefix or "hwy" in prefix:
        scope = "highway"
    elif "city" in prefix or "urban" in prefix:
        scope = "city"
    normalized = re.sub(
        r"\b(?:combined|city|urban|highway|hwy)\s+(?=mpg|miles\s+per\s+gallon)",
        "",
        q,
    )
    parsed = _extract_labeled_range(
        normalized,
        r"mpg|miles\s+per\s+gallon",
        f"{scope}_mpg_min",
        f"{scope}_mpg_max",
        value_digits=r"[0-9]{1,3}",
    )
    plain_mpg = re.search(
        r"\b([0-9]{1,3})\s*(?:mpg|miles\s+per\s+gallon)\b",
        normalized,
    )
    if (
        not parsed
        and plain_mpg
        and _context_mode(q, unit_match.start()) == "preferred"
    ):
        parsed["preferred_combined_mpg_min"] = int(plain_mpg.group(1))
    if parsed and _context_mode(q, unit_match.start()) == "preferred":
        minimum = parsed.pop(f"{scope}_mpg_min", None)
        parsed.pop(f"{scope}_mpg_max", None)
        if minimum is not None:
            parsed["preferred_combined_mpg_min"] = minimum
    result.update(parsed)
    return result


def _extract_cylinders(q: str) -> dict:
    for word, value in {
        "four": "4", "six": "6", "eight": "8", "ten": "10", "twelve": "12",
    }.items():
        q = re.sub(rf"\b{word}\s+cylinders?\b", f"{value} cylinder", q)
    normalized = re.sub(r"\bv\s*([0-9]{1,2})\b", r"\1 cylinder", q)
    normalized = re.sub(r"\binline[- ]?([0-9]{1,2})\b", r"\1 cylinder", normalized)
    result = _extract_labeled_range(
        normalized,
        r"cylinders?|cyl",
        "engine_cylinders_min",
        "engine_cylinders_max",
        value_digits=r"[0-9]{1,2}",
    )
    if not result and (match := re.search(r"\b([0-9]{1,2})\s*(?:cylinders?|cyl)\b", normalized)):
        value = int(match.group(1))
        result["engine_cylinders_min"] = result["engine_cylinders_max"] = value
    return result


def _extract_doors(q: str) -> dict:
    normalized = (
        q.replace("two-door", "2 door")
        .replace("two door", "2 door")
        .replace("three-door", "3 door")
        .replace("three door", "3 door")
        .replace("four-door", "4 door")
        .replace("four door", "4 door")
        .replace("five-door", "5 door")
        .replace("five door", "5 door")
    )
    normalized = re.sub(r"\b([2-5])[- ]doors?\b", r"\1 door", normalized)
    result = _extract_labeled_range(
        normalized,
        r"doors?",
        "number_of_doors_min",
        "number_of_doors_max",
        value_digits=r"[2-5]",
    )
    if not result and (match := re.search(r"\b([2-5])\s*doors?\b", normalized)):
        value = int(match.group(1))
        result["number_of_doors_min"] = result["number_of_doors_max"] = value
    return result


def _find_mentions(q: str, entries: list[tuple[str, str]]) -> list[tuple[int, int, str, str]]:
    """Return non-overlapping longest token mentions with their context mode."""
    matches = []
    occupied: list[tuple[int, int]] = []
    for token, value in sorted(entries, key=lambda item: len(item[0]), reverse=True):
        for match in re.finditer(r"\b" + re.escape(token) + r"\b", q):
            if any(match.start() < end and match.end() > start for start, end in occupied):
                continue
            occupied.append(match.span())
            matches.append((match.start(), match.end(), value, _context_mode(q, match.start())))
    return sorted(matches)


def _detect_makes(q: str) -> dict:
    entries = [(make, CANONICAL_MAKES.get(make, make)) for make in MAKES]
    entries.extend(MAKE_ALIASES.items())
    mentions = _find_mentions(q, entries)
    hard = _unique(value for _, _, value, mode in mentions if mode == "hard")
    preferred = _unique(value for _, _, value, mode in mentions if mode == "preferred")
    excluded = _unique(value for _, _, value, mode in mentions if mode == "excluded")
    hard = [value for value in hard if value not in excluded]
    if preferred and hard and re.search(r"\bprefer(?:ably)?\b", q):
        preferred = _unique(preferred + hard)
        hard = []
    result = {}
    if len(hard) == 1:
        result["make"] = hard[0]
    elif hard:
        result["makes"] = hard
    if preferred:
        result["preferred_makes"] = preferred
    if excluded:
        result["excluded_makes"] = excluded
    return result


@lru_cache(maxsize=1)
def _catalog_models() -> dict[str, tuple[str, ...]]:
    models: dict[str, set[str]] = {}
    try:
        with (ROOT / "data" / "cars_clean.json").open(encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                make, model = str(row.get("make", "")), str(row.get("model", ""))
                if make and model:
                    models.setdefault(make.casefold(), set()).add(model)
    except (OSError, ValueError):
        return {}
    return {
        make: tuple(sorted(values, key=lambda value: len(value), reverse=True))
        for make, values in models.items()
    }


def _detect_models(q: str, make_filters: dict) -> dict:
    catalog = _catalog_models()
    makes = []
    for field in ("make", "makes", "preferred_makes", "excluded_makes"):
        value = make_filters.get(field)
        makes.extend(value if isinstance(value, list) else ([value] if value else []))
    candidates = []
    for make in makes:
        candidates.extend(catalog.get(make.casefold(), ()))
    if not candidates:
        candidates = [model for values in catalog.values() for model in values]
    generic_without_make = {
        "armada", "coupe", "edge", "element", "escape", "fit", "focus",
        "flex", "fusion", "journey", "pilot", "quest", "spark", "truck", "van",
    }

    normalized_query = re.sub(r"[^a-z0-9]+", " ", q).strip()
    matches = []
    occupied = []
    for model in sorted(set(candidates), key=len, reverse=True):
        normalized_model = re.sub(r"[^a-z0-9]+", " ", model.casefold()).strip()
        if len(normalized_model) < 2:
            continue
        if normalized_model in generic_without_make:
            continue
        if not re.search(r"[a-z]", normalized_model):
            make_tokens = [re.escape(make) for make in makes]
            if not make_tokens or not re.search(
                rf"\b(?:{'|'.join(make_tokens)})\s+{re.escape(normalized_model)}\b",
                normalized_query,
            ):
                continue
        if not makes and len(q.split()) > 8:
            continue
        for match in re.finditer(r"\b" + re.escape(normalized_model) + r"\b", normalized_query):
            if any(match.start() < end and match.end() > start for start, end in occupied):
                continue
            # Very short model names are accepted only with an explicit make.
            if len(normalized_model) <= 2 and not makes:
                continue
            occupied.append(match.span())
            matches.append((match.start(), model.casefold(), _context_mode(normalized_query, match.start())))
    matches.sort()
    hard = _unique(value for _, value, mode in matches if mode == "hard")
    excluded = _unique(value for _, value, mode in matches if mode == "excluded")
    hard = [value for value in hard if value not in excluded]
    result = {}
    if len(hard) == 1:
        result["model"] = hard[0]
    elif hard:
        result["models"] = hard
    if excluded:
        result["excluded_models"] = excluded
    return result


def _categorical_mentions(q: str, patterns, hard_field, preferred_field, excluded_field):
    hard, preferred, excluded = [], [], []
    occupied = []
    for pattern, values in patterns:
        for match in re.finditer(pattern, q):
            if any(match.start() < end and match.end() > start for start, end in occupied):
                continue
            occupied.append(match.span())
            mode = _context_mode(q, match.start())
            target = {"hard": hard, "preferred": preferred, "excluded": excluded}[mode]
            target.extend(values if isinstance(values, list) else [values])
    excluded = _unique(excluded)
    hard = [value for value in _unique(hard) if value not in excluded]
    result = {}
    if hard:
        result[hard_field] = hard
    if preferred:
        result[preferred_field] = _unique(preferred)
    if excluded:
        result[excluded_field] = excluded
    return result


def _detect_transmissions(q: str) -> dict:
    # "manual or automatic is fine" is an explicit absence of preference.
    if re.search(r"\bmanual\s+(?:(?:or|/)\s+)?automatic(?:\s+is\s+fine)?\b", q):
        return {}
    parsed = _categorical_mentions(
        q,
        TRANSMISSION_PATTERNS,
        "transmission_types",
        "preferred_transmission_types",
        "excluded_transmission_types",
    )
    hard = parsed.pop("transmission_types", [])
    # There is no dedicated preferred-transmission field; keep the preference
    # visible but non-enforcing in ranking_preferences.
    preferred = parsed.pop("preferred_transmission_types", [])
    if len(hard) == 1:
        parsed["transmission_type"] = hard[0]
    elif hard:
        parsed["transmission_types"] = hard
    if preferred:
        parsed.setdefault("ranking_preferences", []).extend(
            f"transmission:{value}" for value in preferred
        )
    return parsed


def _detect_powertrains(q: str, make_filters: dict) -> dict:
    parsed = _categorical_mentions(
        q,
        POWERTRAIN_PATTERNS,
        "powertrains",
        "preferred_powertrains",
        "excluded_powertrains",
    )
    hard = parsed.pop("powertrains", [])
    if len(hard) == 1 and hard[0] in {"electric", "diesel"}:
        parsed["engine_fuel_type"] = hard[0]
    elif len(hard) == 1 and hard[0] == "hybrid":
        parsed["market_categories"] = ["Hybrid"]
    elif hard:
        parsed["powertrains"] = hard
    makes = [make_filters.get("make"), *(make_filters.get("makes") or [])]
    if "tesla" in makes and not parsed.get("excluded_powertrains"):
        parsed.setdefault("engine_fuel_type", "electric")
    return parsed


def _detect_market_categories(q: str) -> dict:
    hard, preferred, excluded = [], [], []
    patterns = [
        (r"\b(?:luxury|high[- ]end)\b", "Luxury"),
        (r"\b(?:high[- ]performance|performance)\b", "Performance"),
        (r"\b(?:exotic|supercar)\b", "Exotic"),
        (r"\bfactory[- ]tuned?\b", "Factory Tuner"),
    ]
    for pattern, value in patterns:
        for match in re.finditer(pattern, q):
            if re.search(
                r"\bmore\s+than\s*$",
                q[max(0, match.start() - 20):match.start()],
            ):
                continue
            mode = _context_mode(q, match.start())
            {"hard": hard, "preferred": preferred, "excluded": excluded}[mode].append(value)
    result = {}
    if hard:
        result["market_categories"] = _unique(hard)
    if preferred:
        result["preferred_market_categories"] = _unique(preferred)
    if excluded:
        result["excluded_market_categories"] = _unique(excluded)
    return result


def _detect_ranking_preferences(q: str) -> list[str]:
    preferences = []
    patterns = [
        (r"\b(?:affordable|cheap|budget[- ]friendly|good\s+value|low\s+cost|"
         r"college\s+student|first[- ]time\s+buyer)\b", "affordability"),
        (r"\b(?:fuel[- ]efficient|fuel\s+economy|good\s+(?:gas\s+mileage|mpg)|"
         r"gas\s+saver|commuter?|commuting|daily\s+driver)\b", "fuel_economy"),
        (r"\b(?:city\s+driving|urban\s+driving|short\s+trips?)\b", "city_driving"),
        (r"\b(?:highway|freeway|road\s+trips?|long[- ]distance)\b", "highway_driving"),
        (r"\b(?:sporty|fast(?:est)?|quick|fun\s+to\s+drive|powerful|driving\s+dynamics|"
         r"weekend\s+car)\b", "performance"),
        (r"\b(?:newest|latest|recent|late[- ]model|newer\s+tech)\b", "newer"),
        (r"\b(?:snow|ice|winter|all[- ]weather|mountain\s+roads?)\b", "all_weather"),
        (r"\b(?:family|kids?|children|baby|babies|car\s+seats?|roomy|spacious)\b", "family_space"),
        (r"\b(?:cargo|trunk|luggage|camping\s+gear|dogs?|pets?|roomy|spacious)\b", "cargo_space"),
        (r"\b(?:small|compact|easy\s+to\s+park)\b", "compact"),
        (r"\b(?:luxurious|premium\s+interior|quiet\s+ride)\b", "luxury"),
    ]
    for pattern, name in patterns:
        if re.search(pattern, q):
            preferences.append(name)
    return _unique(preferences)


def _unsupported_preferences(q: str) -> list[str]:
    checks = [
        (r"\b(?:reliable|reliability|last\s+(?:me\s+)?many\s+years?|200k\+?\s*miles)\b", "reliability history"),
        (r"\b(?:safe|safety|crash[- ]?test|top\s+safety\s+pick)\b", "safety ratings"),
        (r"\b(?:tow|towing|trailer|boat|camper|payload|tongue\s+weight)\b", "towing and payload"),
        (r"\b(?:third|3rd)\s+row\b|\b[5-9]\s+seats?\b|\bseating\s+capacity\b", "seating capacity"),
        (r"\b(?:car\s*play|android\s+auto|sunroof|moonroof|heated\s+seats?|ventilated\s+seats?|"
         r"blind[- ]spot|backup\s+camera|rear[- ]view\s+camera|parking\s+sensors?|"
         r"adaptive\s+cruise|lane\s+departure|navigation|bluetooth)\b", "installed features"),
        (r"\b(?:under|below|less\s+than|fewer\s+than)\s*[0-9,]+\s*(?:k\s*)?miles\b|"
         r"\b(?:odometer|listing\s+mileage|low\s+mileage)\b", "listing mileage"),
        (r"\b(?:new|used|pre[- ]owned|cpo|certified\s+pre[- ]owned)\s+"
         r"(?:car|vehicle|suv|crossover|truck|sedan|hatchback|wagon|minivan)\b|"
         r"\b(?:new\s+or\s+used|used\s+or\s+new)\b|\b(?:open\s+to|buy(?:ing)?)\s+"
         r"(?:new|used|pre[- ]owned|cpo)\b", "vehicle condition"),
        (r"\b(?:blue|black|white|silver|gray|grey|red|green|orange|yellow|pink|purple)\s+"
         r"(?:car|vehicle|suv|crossover|truck|sedan|hatchback|wagon|minivan|"
         r"paint|exterior|interior)\b|\b(?:exterior|interior)\s+colou?r\b", "color"),
        (r"\b(?:local|near\s+me|within\s+[0-9]+\s+miles?|zip\s*code|"
         r"local\s+inventory|in\s+my\s+area)\b", "location and distance"),
        (r"\b(?:maintenance|repair\s+costs?|insurance|resale|depreciation|"
         r"total\s+cost\s+of\s+ownership|tco|cheap\s+to\s+own)\b", "ownership costs"),
        (r"\b(?:ev\s+range|electric\s+range|charging|charger|charge\s+at\s+home|battery\s+range)\b", "EV range and charging"),
        (r"\b(?:ground\s+clearance|off[- ]road|rock\s+crawling)\b", "off-road capability"),
        (r"\b(?:comfortable|comfort|smooth\s+ride|quiet\s+ride|road\s+noise|seat\s+comfort)\b", "ride comfort"),
        (r"\b(?:monthly|per\s+month|a\s+month|/mo|payment|apr|interest\s+rate|down\s+payment)\b", "financing"),
        (r"\b(?:accident|clean\s+title|carfax|vehicle\s+history|one[- ]owner)\b", "listing history"),
    ]
    return [label for pattern, label in checks if re.search(pattern, q)]


def detect_intents(query: str) -> dict:
    """Backward-compatible intent surface used by the legacy RAG retriever."""
    q = _normalize(query)
    makes = _detect_makes(q)
    style_labels = []
    for pattern, values in STYLE_PATTERNS:
        if re.search(pattern, q):
            label = values[0].casefold()
            if "suv" in label:
                label = "suv"
            elif "pickup" in label:
                label = "truck"
            elif "hatchback" in label:
                label = "hatchback"
            style_labels.append(label)
    transmission_choice = bool(re.search(r"manual\s+(?:or|/)\s+automatic", q))
    return {
        "body_styles": _unique(style_labels),
        "sport": bool(re.search(r"\b(?:sporty|sport|fast|performance|powerful|horsepower)\b", q)),
        "affordable": bool(re.search(r"\b(?:affordable|cheap|budget|good\s+value)\b", q)),
        "fuel_efficient": bool(re.search(r"\b(?:fuel[- ]efficient|fuel\s+economy|good\s+mpg|mpg|commut)\w*", q)),
        "luxury": bool(re.search(r"\b(?:luxury|premium|comfortable|high[- ]end)\b", q)),
        "manual": "manual" in q and not transmission_choice and not re.search(r"\bnot\s+(?:a\s+)?manual\b", q),
        "automatic": "automatic" in q and not transmission_choice and not re.search(r"\bnot\s+(?:an?\s+)?automatic\b", q),
        "electric": bool(re.search(r"\b(?:electric|ev)\b", q)) and not re.search(r"\b(?:not|no)\s+(?:an?\s+)?(?:electric|ev)\b", q),
        "hybrid": "hybrid" in q,
        "diesel": "diesel" in q and not re.search(r"\b(?:not|no)\s+diesel\b", q),
        "make": makes.get("make"),
        "model": None,
    }


def parse_query(query: str) -> SearchFilters:
    q = _normalize(query)
    filters: dict = {"page": 1, "size": 20}

    for extractor in (
        _extract_prices,
        _extract_years,
        _extract_horsepower,
        _extract_mpg,
        _extract_cylinders,
        _extract_doors,
    ):
        filters.update(extractor(q))

    make_filters = _detect_makes(q)
    filters.update(make_filters)
    filters.update(_detect_models(q, make_filters))
    filters.update(_categorical_mentions(
        q,
        STYLE_PATTERNS,
        "vehicle_styles",
        "preferred_vehicle_styles",
        "excluded_vehicle_styles",
    ))
    filters.update(_categorical_mentions(
        q,
        SIZE_PATTERNS,
        "vehicle_sizes",
        "preferred_vehicle_sizes",
        "excluded_vehicle_sizes",
    ))
    # SearchFilters has no excluded_vehicle_sizes field because the current
    # catalog's three coarse size buckets make negative size language too
    # ambiguous. Preserve it as an unsupported preference instead.
    excluded_sizes = filters.pop("excluded_vehicle_sizes", [])
    filters.update(_categorical_mentions(
        q,
        DRIVETRAIN_PATTERNS,
        "driven_wheels",
        "preferred_driven_wheels",
        "excluded_driven_wheels",
    ))

    transmission = _detect_transmissions(q)
    extra_rank = transmission.pop("ranking_preferences", [])
    filters.update(transmission)
    filters.update(_detect_powertrains(q, make_filters))

    market = _detect_market_categories(q)
    # Hybrid detection may already have created a market-category constraint.
    if market.get("market_categories") and filters.get("market_categories"):
        market["market_categories"] = _unique(
            filters["market_categories"] + market["market_categories"]
        )
    filters.update(market)

    ranking = _detect_ranking_preferences(q) + extra_rank
    if re.search(
        r"\b(?:cheapest|cheaper|lowest[- ]price|lower[- ]priced|least\s+expensive)\b",
        q,
    ):
        filters.update(sort="price", order="asc")
    elif re.search(
        r"\b(?:most|more)\s+fuel[- ]efficient\b|\b(?:best|higher|highest)\s+mpg\b",
        q,
    ):
        filters.update(sort="combined_mpg", order="desc")
    elif re.search(
        r"\b(?:fastest|faster|(?:most|more)\s+powerful|"
        r"(?:higher|highest)\s+horsepower)\b",
        q,
    ):
        filters.update(sort="hp", order="desc")
    elif re.search(r"\b(?:newest|newer|latest\s+model)\b", q):
        filters.update(sort="year", order="desc")

    if ranking:
        filters["ranking_preferences"] = _unique(ranking)
    unsupported = _unsupported_preferences(q)
    if excluded_sizes:
        unsupported.append("negative vehicle-size preference")
    if re.search(r"\b(?:plug[- ]?in(?:\s+hybrid)?|phev)\b", q):
        unsupported.append("plug-in capability")
    if re.search(r"\bcvt\b", q):
        unsupported.append("CVT transmission subtype")
    if unsupported:
        filters["unsupported_preferences"] = _unique(unsupported)

    structured = {
        key for key, value in filters.items()
        if key not in {"page", "size", "sort", "order", "unsupported_preferences"}
        and value not in (None, [], "")
    }
    # Unknown short keyword queries can still use the catalog text analyzer.
    # Long natural-language paragraphs are not forwarded wholesale because
    # filler words would suppress otherwise valid structured matches.
    if not structured and not unsupported and len(q.split()) <= 8:
        filters["q"] = query.strip()
    return SearchFilters(**filters)
