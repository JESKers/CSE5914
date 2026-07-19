import json
from pathlib import Path

from evaluation.run_evaluation import FILTER_FIELDS, _constraint_violations, evaluate_parser


def test_labeled_query_set_is_large_unique_and_well_formed():
    cases = json.loads(Path("evaluation/queries.json").read_text(encoding="utf-8"))
    ids = [case["id"] for case in cases]

    assert len(cases) >= 100
    assert len(ids) == len(set(ids))
    for case in cases:
        assert case["query"].strip()
        assert case["tags"]
        assert set(case["expected_filters"]).issubset(FILTER_FIELDS)


def test_parser_evaluation_counts_exact_matches_and_mismatches():
    metrics, rows = evaluate_parser([
        {"id": "pass", "query": "Toyota under $30k", "expected_filters": {"make": "toyota", "price_max": 30000}, "tags": ["demo"]},
        {"id": "fail", "query": "Toyota", "expected_filters": {"make": "ford"}, "tags": ["demo"]},
    ])

    assert metrics["cases"] == 2
    assert metrics["passed"] == 1
    assert metrics["tags"]["demo"]["exact_match_rate"] == 0.5
    assert rows[1]["mismatches"]["make"] == {"expected": "ford", "actual": "toyota"}


def test_constraint_violation_check_covers_numeric_and_exact_fields():
    car = {"make": "Ford", "year": 2018, "msrp": 52000, "engine_hp": 250}
    filters = {"make": "ford", "year_min": 2020, "price_max": 50000, "hp_min": 300}

    assert _constraint_violations(car, filters) == ["year_min", "price_max", "hp_min"]
