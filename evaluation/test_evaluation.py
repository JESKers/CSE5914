import json
from pathlib import Path

from evaluation.run_evaluation import FILTER_FIELDS, _constraint_violations, _is_relevant, evaluate_parser


def test_labeled_query_set_is_large_unique_and_well_formed():
    cases = json.loads(Path("evaluation/queries.json").read_text(encoding="utf-8"))
    ids = [case["id"] for case in cases]

    assert len(cases) >= 300
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
    car = {
        "make": "Ford", "year": 2018, "msrp": 52000, "engine_hp": 250,
        "driven_wheels": "rear wheel drive", "number_of_doors": 2,
        "combined_mpg": 20,
    }
    filters = {
        "make": "ford", "year_min": 2020, "price_max": 50000, "hp_min": 300,
        "driven_wheels": ["all wheel drive"], "number_of_doors_min": 4,
        "combined_mpg_min": 30,
    }

    assert _constraint_violations(car, filters) == [
        "year_min", "price_max", "hp_min", "number_of_doors_min",
        "combined_mpg_min", "driven_wheels",
    ]


def test_constraint_violation_check_covers_categories_and_powertrains():
    car = {
        "engine_fuel_type": "premium unleaded",
        "market_category": "Luxury,Performance",
    }

    assert _constraint_violations(
        car,
        {
            "market_categories": ["Hybrid"],
            "excluded_market_categories": ["Luxury"],
            "powertrains": ["diesel"],
            "excluded_powertrains": ["gasoline"],
        },
    ) == [
        "market_categories",
        "excluded_market_categories",
        "powertrains",
        "excluded_powertrains",
    ]


def test_relevance_label_checks_top_result_attributes():
    car = {"make": "Honda", "vehicle_style": "4dr SUV", "msrp": 28000,
           "engine_hp": 220, "city_mpg": 26, "highway_mpg": 32}
    assert _is_relevant(car, {"vehicle_styles_any": ["suv"], "max_msrp": 30000})
    assert not _is_relevant(car, {"min_hp": 300})
