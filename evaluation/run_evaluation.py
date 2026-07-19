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
    "make", "model", "year_min", "year_max", "price_min", "price_max",
    "hp_min", "hp_max", "engine_fuel_type", "transmission_type",
)


def _equal(actual, expected) -> bool:
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.casefold() == expected.casefold()
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
    return violations


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
        rows.append({
            "id": case["id"], "status": status, "result_count": len(body.get("results", [])),
            "constraint_violations": violations, "latency_ms": round(latency_ms, 3),
            "error": error,
        })

    successful = [row for row in rows if row["status"] == 200]
    metrics = {
        "cases": len(rows), "successful_requests": len(successful),
        "constraint_violations": sum(len(row["constraint_violations"]) for row in rows),
        "empty_result_rate": round(sum(row["result_count"] == 0 for row in successful) / len(successful), 4) if successful else None,
        "mean_latency_ms": round(mean(row["latency_ms"] for row in successful), 3) if successful else None,
    }
    return metrics, rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, default=Path(__file__).with_name("queries.json"))
    parser.add_argument("--api-url", help="Also evaluate a running backend, e.g. http://localhost:8000")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "results" / "latest.json")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
