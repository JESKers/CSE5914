"""Endpoint tests for /search and /facets — no live ES required.

The search core is monkeypatched so these run in CI without Elasticsearch;
they exercise the FastAPI layer: param parsing, the response envelope,
validation (400 on bad ranges, 422 on bad paging), and empty results.

Run from the repo root:  pytest
"""
import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.schemas import SearchFilters

client = TestClient(main.app)

_SAMPLE_CAR = {
    "id": "1", "make": "BMW", "model": "M4", "year": 2016, "msrp": 65700.0,
    "engine_hp": 425, "engine_fuel_type": "premium unleaded (required)",
    "transmission_type": "MANUAL", "vehicle_style": "Coupe",
    "highway_mpg": 26, "city_mpg": 17,
}


@pytest.fixture
def fake_search(monkeypatch):
    """Capture the SearchFilters the endpoint builds and return a canned result."""
    captured = {}

    def _fake(f: SearchFilters):
        captured["filters"] = f
        return {"total": 1, "page": f.page, "size": f.size, "results": [_SAMPLE_CAR]}

    monkeypatch.setattr(main.search_service, "search", _fake)
    return captured


def test_search_envelope(fake_search):
    r = client.get("/search?make=BMW&price_max=70000&q=coupe&sort=hp")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["page"] == 1 and body["size"] == 20
    assert body["results"][0]["make"] == "BMW"
    # query_echo reflects applied filters, dropping unset ones
    assert body["query_echo"]["make"] == "BMW"
    assert "model" not in body["query_echo"]
    # params were parsed into the filter object
    f = fake_search["filters"]
    assert f.make == "BMW" and f.price_max == 70000 and f.q == "coupe" and f.sort == "hp"


def test_search_empty_results_is_200(monkeypatch):
    monkeypatch.setattr(
        main.search_service, "search",
        lambda f: {"total": 0, "page": f.page, "size": f.size, "results": []},
    )
    r = client.get("/search?make=Nonesuch")
    assert r.status_code == 200
    assert r.json() == {"results": [], "total": 0, "page": 1, "size": 20,
                        "query_echo": {"make": "Nonesuch", "sort": "popularity",
                                       "order": "desc", "page": 1, "size": 20}}


def test_search_pagination_params(fake_search):
    client.get("/search?page=3&size=5")
    f = fake_search["filters"]
    assert f.page == 3 and f.size == 5


@pytest.mark.parametrize("qs", [
    "year_min=2020&year_max=2010",
    "price_min=50000&price_max=10000",
    "hp_min=500&hp_max=100",
])
def test_inverted_range_returns_400(fake_search, qs):
    r = client.get(f"/search?{qs}")
    assert r.status_code == 400
    assert "must not exceed" in r.json()["detail"]


@pytest.mark.parametrize("qs", ["page=0", "size=0", "size=101"])
def test_bad_paging_returns_422(qs):
    # FastAPI Query constraints reject out-of-range paging before our code runs.
    assert client.get(f"/search?{qs}").status_code == 422


def test_equal_bounds_allowed(fake_search):
    # min == max is a valid (single-value) range, not an inversion.
    assert client.get("/search?year_min=2016&year_max=2016").status_code == 200


def test_facets(monkeypatch):
    monkeypatch.setattr(main.search_service, "facets", lambda: {
        "makes": [{"key": "Chevrolet", "count": 1123}],
        "transmissions": [{"key": "AUTOMATIC", "count": 8266}],
        "fuel_types": [{"key": "regular unleaded", "count": 7172}],
        "years": [2017, 2016, 2015],
    })
    body = client.get("/facets").json()
    assert body["makes"][0] == {"key": "Chevrolet", "count": 1123}
    assert body["transmissions"][0]["key"] == "AUTOMATIC"
    assert body["years"] == [2017, 2016, 2015]


def test_models_for_make(monkeypatch):
    captured = {}

    def _fake(make):
        captured["make"] = make
        return ["1 Series", "3 Series", "M4"]

    monkeypatch.setattr(main.search_service, "models", _fake)
    body = client.get("/models?make=BMW").json()
    assert body == {"make": "BMW", "models": ["1 Series", "3 Series", "M4"]}
    assert captured["make"] == "BMW"


def test_models_requires_make():
    # `make` is required -> 422 when omitted or blank.
    assert client.get("/models").status_code == 422
    assert client.get("/models?make=").status_code == 422
