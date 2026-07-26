"""Evaluate NL filter parsing and, optionally, the live recommendation API.

Run from the repository root:
    python evaluation/run_evaluation.py
    python evaluation/run_evaluation.py --api-url http://localhost:8000
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag import parser as rag_parser  # noqa: E402

# Parser scoring must be reproducible without a live Elasticsearch index. Model
# recognition that depends on the catalog is covered by the opt-in API run.
rag_parser.search_service = None
parse_query = rag_parser.parse_query


FILTER_FIELDS = (
    "make", "model", "makes", "models", "excluded_makes", "excluded_models",
    "year_min", "year_max", "price_min", "price_max", "hp_min", "hp_max",
    "engine_cylinders_min", "engine_cylinders_max",
    "number_of_doors_min", "number_of_doors_max",
    "city_mpg_min", "city_mpg_max", "highway_mpg_min", "highway_mpg_max",
    "combined_mpg_min", "combined_mpg_max",
    "engine_fuel_type", "transmission_type", "transmission_types",
    "excluded_transmission_types", "powertrains", "excluded_powertrains",
    "vehicle_styles", "preferred_vehicle_styles", "excluded_vehicle_styles",
    "vehicle_sizes", "preferred_vehicle_sizes",
    "driven_wheels", "preferred_driven_wheels", "excluded_driven_wheels",
    "market_categories", "preferred_market_categories", "excluded_market_categories",
    "preferred_price_max", "preferred_year_min", "preferred_hp_min",
    "preferred_combined_mpg_min", "preferred_makes", "preferred_powertrains",
    "ranking_preferences", "unsupported_preferences",
)


def _equal(actual, expected) -> bool:
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.casefold() == expected.casefold()
    if isinstance(actual, list) and isinstance(expected, list):
        normalize = lambda value: value.casefold() if isinstance(value, str) else value
        return sorted(map(normalize, actual), key=str) == sorted(map(normalize, expected), key=str)
    return actual == expected


def evaluate_parser(cases: list[dict]) -> tuple[dict, list[dict]]:
    field_counts = defaultdict(Counter)
    rows = []
    for case in cases:
        started = time.perf_counter()
        error = None
        try:
            parsed = parse_query(case["query"]).model_dump(exclude_none=True)
        except Exception as exc:  # evaluation must record failures, not stop the run
            parsed = {}
            error = f"{type(exc).__name__}: {exc}"
        latency_ms = (time.perf_counter() - started) * 1000

        expected = case.get("expected_filters", {})
        mismatches = {}
        for field in FILTER_FIELDS:
            actual_value = parsed.get(field)
            expected_value = expected.get(field)
            if expected_value is None and actual_value is None:
                field_counts[field]["tn"] += 1
            elif expected_value is None:
                field_counts[field]["fp"] += 1
                mismatches[field] = {"expected": None, "actual": actual_value}
            elif actual_value is None:
                field_counts[field]["fn"] += 1
                mismatches[field] = {"expected": expected_value, "actual": None}
            elif _equal(actual_value, expected_value):
                field_counts[field]["tp"] += 1
            else:
                field_counts[field]["wrong"] += 1
                mismatches[field] = {"expected": expected_value, "actual": actual_value}

        rows.append({
            "id": case["id"], "query": case["query"], "tags": case.get("tags", []),
            "passed": not mismatches and error is None, "expected_filters": expected,
            "parsed_filters": {k: parsed.get(k) for k in FILTER_FIELDS if parsed.get(k) is not None},
            "mismatches": mismatches, "error": error, "latency_ms": round(latency_ms, 3),
        })

    passed = sum(row["passed"] for row in rows)
    tag_totals = Counter(tag for row in rows for tag in row["tags"])
    tag_passed = Counter(tag for row in rows if row["passed"] for tag in row["tags"])
    metrics = {
        "cases": len(rows),
        "passed": passed,
        "exact_match_rate": round(passed / len(rows), 4) if rows else 0,
        "mean_latency_ms": round(mean(row["latency_ms"] for row in rows), 3) if rows else 0,
        "tags": {
            tag: {
                "cases": total,
                "passed": tag_passed[tag],
                "exact_match_rate": round(tag_passed[tag] / total, 4),
            }
            for tag, total in sorted(tag_totals.items())
        },
        "fields": {field: dict(counts) for field, counts in field_counts.items()},
    }
    return metrics, rows


def _constraint_violations(car: dict, filters: dict) -> list[str]:
    violations = []
    comparisons = (
        ("year_min", "year", lambda a, w: a >= w),
        ("year_max", "year", lambda a, w: a <= w),
        ("price_min", "msrp", lambda a, w: a >= w),
        ("price_max", "msrp", lambda a, w: a <= w),
        ("hp_min", "engine_hp", lambda a, w: a >= w),
        ("hp_max", "engine_hp", lambda a, w: a <= w),
        ("engine_cylinders_min", "engine_cylinders", lambda a, w: a >= w),
        ("engine_cylinders_max", "engine_cylinders", lambda a, w: a <= w),
        ("number_of_doors_min", "number_of_doors", lambda a, w: a >= w),
        ("number_of_doors_max", "number_of_doors", lambda a, w: a <= w),
        ("city_mpg_min", "city_mpg", lambda a, w: a >= w),
        ("city_mpg_max", "city_mpg", lambda a, w: a <= w),
        ("highway_mpg_min", "highway_mpg", lambda a, w: a >= w),
        ("highway_mpg_max", "highway_mpg", lambda a, w: a <= w),
        ("combined_mpg_min", "combined_mpg", lambda a, w: a >= w),
        ("combined_mpg_max", "combined_mpg", lambda a, w: a <= w),
    )
    for filter_key, car_key, predicate in comparisons:
        if filter_key in filters:
            actual = car.get(car_key)
            if actual is None or not predicate(actual, filters[filter_key]):
                violations.append(filter_key)
    for field in ("make", "model", "transmission_type"):
        if field in filters and str(car.get(field, "")).casefold() != str(filters[field]).casefold():
            violations.append(field)
    if "engine_fuel_type" in filters and str(filters["engine_fuel_type"]).casefold() not in str(car.get("engine_fuel_type", "")).casefold():
        violations.append("engine_fuel_type")
    for filter_key, car_key in (
        ("makes", "make"), ("models", "model"),
        ("transmission_types", "transmission_type"),
        ("vehicle_styles", "vehicle_style"), ("vehicle_sizes", "vehicle_size"),
        ("driven_wheels", "driven_wheels"),
    ):
        if filter_key in filters and str(car.get(car_key, "")).casefold() not in {
            str(value).casefold() for value in filters[filter_key]
        }:
            violations.append(filter_key)
    for filter_key, car_key in (
        ("excluded_makes", "make"), ("excluded_models", "model"),
        ("excluded_transmission_types", "transmission_type"),
        ("excluded_vehicle_styles", "vehicle_style"),
        ("excluded_driven_wheels", "driven_wheels"),
    ):
        if filter_key in filters and str(car.get(car_key, "")).casefold() in {
            str(value).casefold() for value in filters[filter_key]
        }:
            violations.append(filter_key)
    category = str(car.get("market_category", "")).casefold()
    if "market_categories" in filters and not any(
        str(value).casefold() in category for value in filters["market_categories"]
    ):
        violations.append("market_categories")
    if "excluded_market_categories" in filters and any(
        str(value).casefold() in category
        for value in filters["excluded_market_categories"]
    ):
        violations.append("excluded_market_categories")

    def matches_powertrain(value: str) -> bool:
        fuel = str(car.get("engine_fuel_type", "")).casefold()
        normalized = str(value).casefold()
        if normalized == "hybrid":
            return "hybrid" in category
        if normalized == "gasoline":
            return "unleaded" in fuel
        if normalized == "flex-fuel":
            return "flex-fuel" in fuel
        return normalized in fuel

    if "powertrains" in filters and not any(
        matches_powertrain(value) for value in filters["powertrains"]
    ):
        violations.append("powertrains")
    if "excluded_powertrains" in filters and any(
        matches_powertrain(value) for value in filters["excluded_powertrains"]
    ):
        violations.append("excluded_powertrains")
    return violations


def _is_relevant(car: dict, label: dict) -> bool:
    style = str(car.get("vehicle_style", "")).casefold()
    make = str(car.get("make", "")).casefold()
    if label.get("vehicle_styles_any") and not any(
        value.casefold() in style for value in label["vehicle_styles_any"]
    ):
        return False
    if label.get("makes_any") and make not in {value.casefold() for value in label["makes_any"]}:
        return False
    numeric = (
        ("max_msrp", "msrp", lambda actual, wanted: actual <= wanted),
        ("min_hp", "engine_hp", lambda actual, wanted: actual >= wanted),
        ("min_city_mpg", "city_mpg", lambda actual, wanted: actual >= wanted),
        ("min_highway_mpg", "highway_mpg", lambda actual, wanted: actual >= wanted),
    )
    return all(
        key not in label or (car.get(field) is not None and predicate(car[field], label[key]))
        for key, field, predicate in numeric
    )


def evaluate_api(cases: list[dict], api_url: str) -> tuple[dict, list[dict]]:
    rows = []
    for case in cases:
        payload = json.dumps({"query": case["query"]}).encode()
        request = urllib.request.Request(
            f"{api_url.rstrip('/')}/recommend", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                status = response.status
                body = json.load(response)
            error = None
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            status, body, error = None, {}, f"{type(exc).__name__}: {exc}"
        latency_ms = (time.perf_counter() - started) * 1000
        filters = body.get("query_echo", {}).get("parsed_filters", {})
        violations = [
            {"vehicle_id": car.get("id"), "fields": _constraint_violations(car, filters)}
            for car in body.get("results", [])
        ]
        violations = [item for item in violations if item["fields"]]
        relevance = case.get("relevance")
        top_five = body.get("results", [])[:5]
        relevant_count = sum(_is_relevant(car, relevance) for car in top_five) if relevance else None
        vpic_statuses = Counter(
            car.get("vpic_evidence", {}).get("status", "missing")
            for car in body.get("results", [])
        )
        rows.append({
            "id": case["id"], "status": status, "result_count": len(body.get("results", [])),
            "constraint_violations": violations, "latency_ms": round(latency_ms, 3),
            "vpic_statuses": dict(vpic_statuses),
            "generation_mode": body.get("generation_mode"), "error": error,
            "relevance_precision_at_5": (
                round(relevant_count / len(top_five), 4) if relevance and top_five else None
            ),
        })

    successful = [row for row in rows if row["status"] == 200]
    relevance_rows = [row for row in successful if row["relevance_precision_at_5"] is not None]
    metrics = {
        "cases": len(rows), "successful_requests": len(successful),
        "constraint_violations": sum(len(row["constraint_violations"]) for row in rows),
        "empty_result_rate": round(sum(row["result_count"] == 0 for row in successful) / len(successful), 4) if successful else None,
        "mean_latency_ms": round(mean(row["latency_ms"] for row in successful), 3) if successful else None,
        "generation_modes": dict(Counter(row["generation_mode"] for row in successful)),
        "vpic_statuses": dict(sum((Counter(row["vpic_statuses"]) for row in successful), Counter())),
        "mean_relevance_precision_at_5": (
            round(mean(row["relevance_precision_at_5"] for row in relevance_rows), 4)
            if relevance_rows else None
        ),
        "relevance_cases": len(relevance_rows),
    }
    return metrics, rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, default=Path(__file__).with_name("queries.json"))
    parser.add_argument("--api-url", help="Also evaluate a running backend, e.g. http://localhost:8000")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "results" / "latest.json")
    parser.add_argument("--min-exact-match-rate", type=float,
                        help="Exit nonzero if parser accuracy falls below this value")
    args = parser.parse_args()

    cases = json.loads(args.queries.read_text(encoding="utf-8"))
    parser_metrics, parser_rows = evaluate_parser(cases)
    report = {"query_file": str(args.queries), "parser": {"metrics": parser_metrics, "cases": parser_rows}}
    if args.api_url:
        api_metrics, api_rows = evaluate_api(cases, args.api_url)
        report["api"] = {"url": args.api_url, "metrics": api_metrics, "cases": api_rows}

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Parser exact matches: {parser_metrics['passed']}/{parser_metrics['cases']} "
          f"({parser_metrics['exact_match_rate']:.1%})")
    print(f"Mean parser latency: {parser_metrics['mean_latency_ms']:.3f} ms")
    if args.api_url:
        print(f"API constraint violations: {report['api']['metrics']['constraint_violations']}")
        print(f"Successful API requests: {report['api']['metrics']['successful_requests']}/{len(cases)}")
    print(f"Detailed report: {args.output}")
    if (args.min_exact_match_rate is not None
            and parser_metrics["exact_match_rate"] < args.min_exact_match_rate):
        print(f"FAILED: exact-match rate is below {args.min_exact_match_rate:.1%}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
