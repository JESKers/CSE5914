"""Unit tests for the query/sort builders — no live ES needed.

Run from the repo root:  pytest

Covers each filter type (term, range, keyword), their combination, sorting,
and edge cases (empty filters, partial ranges, unknown sort key).
"""
from backend.app.schemas import SearchFilters
from search.search_service import _build_query, _build_sort


# --- keyword / full-text -----------------------------------------------------

def test_match_all_when_empty():
    assert _build_query(SearchFilters()) == {"match_all": {}}


def test_keyword_only_uses_multi_match():
    q = _build_query(SearchFilters(q="luxury coupe"))
    bool_q = q["bool"]
    assert bool_q["filter"] == []
    assert any("multi_match" in m for m in bool_q["must"])
    mm = bool_q["must"][0]["multi_match"]
    assert mm["query"] == "luxury coupe"
    assert "text" in mm["fields"]
    assert mm["fuzziness"] == "AUTO"


# --- term filters ------------------------------------------------------------

def test_term_filters_each_field():
    q = _build_query(SearchFilters(
        make="BMW", model="M4",
        engine_fuel_type="premium unleaded (required)",
        transmission_type="MANUAL",
    ))
    filt = q["bool"]["filter"]
    assert {"term": {"make": "BMW"}} in filt
    assert {"term": {"model": "M4"}} in filt
    assert {"term": {"engine_fuel_type": "premium unleaded (required)"}} in filt
    assert {"term": {"transmission_type": "MANUAL"}} in filt
    # no keyword -> must defaults to match_all
    assert q["bool"]["must"] == {"match_all": {}}


# --- range filters -----------------------------------------------------------

def test_range_both_bounds():
    q = _build_query(SearchFilters(year_min=2010, year_max=2015))
    assert {"range": {"year": {"gte": 2010, "lte": 2015}}} in q["bool"]["filter"]


def test_range_lower_bound_only():
    q = _build_query(SearchFilters(hp_min=300))
    assert {"range": {"engine_hp": {"gte": 300}}} in q["bool"]["filter"]


def test_range_upper_bound_only():
    q = _build_query(SearchFilters(price_max=50000))
    assert {"range": {"msrp": {"lte": 50000}}} in q["bool"]["filter"]


def test_all_three_ranges_present():
    q = _build_query(SearchFilters(
        year_min=2012, price_min=10000, price_max=40000, hp_min=200, hp_max=500,
    ))
    filt = q["bool"]["filter"]
    assert {"range": {"year": {"gte": 2012}}} in filt
    assert {"range": {"msrp": {"gte": 10000, "lte": 40000}}} in filt
    assert {"range": {"engine_hp": {"gte": 200, "lte": 500}}} in filt


# --- combined ----------------------------------------------------------------

def test_filters_and_keyword():
    q = _build_query(SearchFilters(make="BMW", price_max=50000, q="coupe"))
    bool_q = q["bool"]
    assert {"term": {"make": "BMW"}} in bool_q["filter"]
    assert {"range": {"msrp": {"lte": 50000}}} in bool_q["filter"]
    assert any("multi_match" in m for m in bool_q["must"])


# --- sorting -----------------------------------------------------------------

def test_sort_maps_alias_and_adds_tiebreaker():
    sort = _build_sort(SearchFilters(sort="price", order="asc"))
    assert sort[0] == {"msrp": {"order": "asc"}}
    assert sort[-1] == {"id": "asc"}  # deterministic pagination tie-breaker


def test_sort_unknown_key_falls_back_to_popularity():
    sort = _build_sort(SearchFilters(sort="bogus"))
    assert sort[0] == {"popularity": {"order": "desc"}}


def test_sort_invalid_order_defaults_to_desc():
    sort = _build_sort(SearchFilters(sort="hp", order="sideways"))
    assert sort[0] == {"engine_hp": {"order": "desc"}}
