"""Unit tests for the query/sort builders — no live ES needed.

Run from the repo root:  pytest

Covers each filter type (term, range, keyword), their combination, sorting,
and edge cases (empty filters, partial ranges, unknown sort key).
"""
from backend.app.schemas import SearchFilters
from search.search_service import _build_query, _build_sort


def _case_insensitive_values(clause, field):
    return [
        item["term"][field]["value"]
        for item in clause["bool"]["should"]
    ]


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
    assert _case_insensitive_values(filt[0], "make") == ["BMW"]
    assert _case_insensitive_values(filt[1], "model") == ["M4"]
    assert _case_insensitive_values(filt[2], "engine_fuel_type") == [
        "premium unleaded (required)"
    ]
    assert _case_insensitive_values(filt[3], "transmission_type") == ["MANUAL"]
    # no keyword -> must defaults to match_all
    assert q["bool"]["must"] == {"match_all": {}}


def test_or_filters_and_exclusions_stay_separate():
    q = _build_query(SearchFilters(
        makes=["Toyota", "Mazda"],
        vehicle_styles=["Sedan", "4dr Hatchback"],
        excluded_makes=["Tesla"],
        excluded_transmission_types=["AUTOMATIC"],
    ))

    assert _case_insensitive_values(q["bool"]["filter"][0], "make") == [
        "Toyota", "Mazda"
    ]
    assert _case_insensitive_values(q["bool"]["filter"][1], "vehicle_style") == [
        "Sedan", "4dr Hatchback"
    ]
    assert _case_insensitive_values(q["bool"]["must_not"][0], "make") == ["Tesla"]
    assert _case_insensitive_values(
        q["bool"]["must_not"][1], "transmission_type"
    ) == ["AUTOMATIC"]


def test_powertrain_filters_map_hybrid_and_gasoline_to_catalog_fields():
    q = _build_query(SearchFilters(powertrains=["hybrid", "gasoline"]))
    clauses = q["bool"]["filter"][0]["bool"]["should"]

    assert clauses[0]["wildcard"]["market_category"]["value"] == "*Hybrid*"
    assert clauses[1]["wildcard"]["engine_fuel_type"]["value"] == "*unleaded*"


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


def test_extended_catalog_ranges_are_enforced():
    q = _build_query(SearchFilters(
        engine_cylinders_min=4,
        engine_cylinders_max=6,
        number_of_doors_min=4,
        city_mpg_min=25,
        highway_mpg_min=32,
        combined_mpg_min=28,
    ))
    filt = q["bool"]["filter"]

    assert {"range": {"engine_cylinders": {"gte": 4, "lte": 6}}} in filt
    assert {"range": {"number_of_doors": {"gte": 4}}} in filt
    assert {"range": {"city_mpg": {"gte": 25}}} in filt
    assert {"range": {"highway_mpg": {"gte": 32}}} in filt
    assert {"range": {"combined_mpg": {"gte": 28}}} in filt


# --- combined ----------------------------------------------------------------

def test_filters_and_keyword():
    q = _build_query(SearchFilters(make="BMW", price_max=50000, q="coupe"))
    bool_q = q["bool"]
    assert _case_insensitive_values(bool_q["filter"][0], "make") == ["BMW"]
    assert {"range": {"msrp": {"lte": 50000}}} in bool_q["filter"]
    assert any("multi_match" in m for m in bool_q["must"])


def test_soft_preferences_boost_without_becoming_filters():
    filters = SearchFilters(
        preferred_price_max=40000,
        preferred_combined_mpg_min=30,
        preferred_makes=["Honda", "Toyota"],
        ranking_preferences=["family_space", "transmission:MANUAL"],
    )
    q = _build_query(filters)

    assert q["bool"]["filter"] == []
    assert {"range": {"msrp": {"lte": 40000, "boost": 3}}} in q["bool"]["should"]
    assert {"range": {"combined_mpg": {"gte": 30, "boost": 3}}} in q["bool"]["should"]
    make_clause = next(
        clause for clause in q["bool"]["should"]
        if "bool" in clause
        and clause["bool"]["should"][0].get("term", {}).get("make")
    )
    assert _case_insensitive_values(make_clause, "make") == ["Honda", "Toyota"]
    transmission_clause = next(
        clause for clause in q["bool"]["should"]
        if "bool" in clause
        and clause["bool"]["should"][0].get("term", {}).get("transmission_type")
    )
    assert _case_insensitive_values(
        transmission_clause, "transmission_type"
    ) == ["MANUAL"]
    assert _build_sort(filters)[0] == {"_score": {"order": "desc"}}


# --- sorting -----------------------------------------------------------------

def test_sort_maps_alias_and_adds_tiebreaker():
    sort = _build_sort(SearchFilters(sort="price", order="asc"))
    assert sort[0] == {"msrp": {"order": "asc"}}
    assert sort[-1] == {"id": "asc"}  # deterministic pagination tie-breaker


def test_sort_unknown_key_falls_back_to_popularity():
    sort = _build_sort(SearchFilters(sort="bogus"))
    assert sort[0] == {"popularity": {"order": "desc"}}


def test_keyword_search_uses_relevance_by_default():
    sort = _build_sort(SearchFilters(q="luxury coupe"))
    assert sort[0] == {"_score": {"order": "desc"}}
    assert sort[1] == {"id": "asc"}


def test_sort_invalid_order_defaults_to_desc():
    sort = _build_sort(SearchFilters(sort="hp", order="sideways"))
    assert sort[0] == {"engine_hp": {"order": "desc"}}
