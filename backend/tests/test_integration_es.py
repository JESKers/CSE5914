"""End-to-end integration tests against a live Elasticsearch.

These are skipped automatically when ES is not reachable, so the default
`pytest` run stays green without Docker. To run them, bring up the stack and
seed the index first:

    docker compose up -d
    docker compose exec backend python -m search.clean_data
    docker compose exec backend python -m search.ingest
    pytest backend/tests/test_integration_es.py -v

They assert the real search behaviour the unit tests can only stub: filters
hit the index, ranges/sorting work, and the "chevy" -> "Chevrolet" synonym
expansion from the index mapping actually fires.
"""
import pytest
from fastapi.testclient import TestClient

from backend.app.es_client import get_es
from backend.app.main import app


def _es_ready() -> bool:
    try:
        es = get_es()
        from backend.app.config import settings
        return es.ping() and es.indices.exists(index=settings.es_index)
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _es_ready(), reason="Elasticsearch not running or `cars` index not seeded"
)

client = TestClient(app)


def test_health_reports_es_up():
    assert client.get("/health").json()["elasticsearch"] is True


def test_make_filter_returns_only_that_make():
    body = client.get("/search?make=BMW&size=10").json()
    assert body["total"] > 0
    assert all(c["make"] == "BMW" for c in body["results"])


def test_price_range_respected():
    body = client.get("/search?price_min=20000&price_max=40000&size=50").json()
    assert all(20000 <= c["msrp"] <= 40000 for c in body["results"])


def test_sort_by_hp_desc_is_monotonic():
    hps = [c["engine_hp"] for c in client.get("/search?sort=hp&order=desc&size=20").json()["results"]]
    assert hps == sorted(hps, reverse=True)


def test_pagination_pages_differ():
    p1 = client.get("/search?sort=price&order=asc&page=1&size=5").json()["results"]
    p2 = client.get("/search?sort=price&order=asc&page=2&size=5").json()["results"]
    assert {c["id"] for c in p1}.isdisjoint({c["id"] for c in p2})


def test_chevy_synonym_matches_chevrolet():
    body = client.get("/search?q=chevy&size=20").json()
    assert any(c["make"] == "Chevrolet" for c in body["results"])


def test_facets_have_buckets():
    body = client.get("/facets").json()
    assert len(body["makes"]) > 0
    assert all("key" in b and "count" in b for b in body["makes"])
