"""Unit tests for the query builder — no live ES needed.

Run from the repo root:  pytest
"""
from backend.app.schemas import SearchFilters
from search.search_service import _build_query


def test_match_all_when_empty():
    assert _build_query(SearchFilters()) == {"match_all": {}}


def test_filters_and_keyword():
    q = _build_query(SearchFilters(make="BMW", price_max=50000, q="coupe"))
    bool_q = q["bool"]
    assert {"term": {"make": "BMW"}} in bool_q["filter"]
    assert {"range": {"msrp": {"lte": 50000}}} in bool_q["filter"]
    assert any("multi_match" in m for m in bool_q["must"])


def test_range_both_bounds():
    q = _build_query(SearchFilters(year_min=2010, year_max=2015))
    assert {"range": {"year": {"gte": 2010, "lte": 2015}}} in q["bool"]["filter"]
