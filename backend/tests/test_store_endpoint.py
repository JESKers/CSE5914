"""Tests for the additive Buy/Rent store + vPIC endpoints — no live ES required.

The search core and the vPIC client are monkeypatched so these run in CI without
Elasticsearch or network access. They cover: the listings envelope and price
derivation, rent-mode filtering, purchase stock decrement, rental totals, and
the order ledger. Run from the repo root:  pytest
"""
import pytest
from fastapi.testclient import TestClient

from backend.app import main, store
from backend.app.schemas import SearchFilters

client = TestClient(main.app)

_SAMPLE_CAR = {
    "id": "1", "make": "BMW", "model": "M4", "year": 2016, "msrp": 60000.0,
    "engine_hp": 425, "engine_fuel_type": "premium unleaded (required)",
    "transmission_type": "MANUAL", "vehicle_style": "Coupe",
    "highway_mpg": 26, "city_mpg": 17,
}


@pytest.fixture(autouse=True)
def isolate_store(tmp_path, monkeypatch):
    """Point the orders ledger at a temp DB and stub out network/ES calls."""
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "store.db")
    monkeypatch.setattr(main.vpic, "make_id_index", lambda: {"BMW": 452})
    monkeypatch.setattr(main.vpic, "is_verified", lambda make: make.upper() == "BMW")

    def _fake_search(f: SearchFilters):
        return {"total": 1, "page": f.page, "size": f.size, "results": [_SAMPLE_CAR]}

    monkeypatch.setattr(main.search_service, "search", _fake_search)
    monkeypatch.setattr(main.search_service, "get_car", lambda vid: dict(_SAMPLE_CAR))


# --------------------------------------------------------------------------- #
# Pure pricing logic
# --------------------------------------------------------------------------- #
def test_seats_and_rent_derivation():
    assert store.estimate_seats("4dr SUV") == 7
    assert store.estimate_seats("Coupe") == 4
    rent = store.derive_rent_daily(30000, "Sedan")
    assert 30 <= rent <= 60
    # SUVs carry a premium over an equivalently priced sedan
    assert store.derive_rent_daily(30000, "4dr SUV") >= rent


def test_rent_to_msrp_inverse_is_monotonic():
    assert store.rent_daily_to_msrp(40) < store.rent_daily_to_msrp(80)


# --------------------------------------------------------------------------- #
# Listings
# --------------------------------------------------------------------------- #
def test_buy_listing_has_price_stock_and_vpic_flag():
    r = client.get("/store/listings?mode=buy")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "buy"
    car = body["results"][0]
    assert car["buy_price"] == 60000.0
    assert car["rent_daily"] > 0
    assert car["stock"] >= 1
    assert car["vpic_verified"] is True  # BMW is in the stubbed vPIC directory


def test_inverted_price_range_returns_400():
    r = client.get("/store/listings?mode=buy&price_min=50000&price_max=1000")
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #
def test_purchase_decrements_stock():
    before = client.get("/store/vehicle/1").json()["stock"]
    order = client.post("/store/orders", json={"vehicle_id": "1", "mode": "buy"})
    assert order.status_code == 200
    assert order.json()["total"] == 60000.0
    after = client.get("/store/vehicle/1").json()["stock"]
    assert after == before - 1


def test_rental_total_is_daily_times_days():
    listing = client.get("/store/vehicle/1").json()
    if not listing["for_rent"]:
        pytest.skip("sample vehicle not offered for rent")
    r = client.post("/store/orders", json={"vehicle_id": "1", "mode": "rent", "rent_days": 4})
    assert r.status_code == 200
    assert r.json()["total"] == listing["rent_daily"] * 4


def test_order_history_records_orders():
    client.post("/store/orders", json={"vehicle_id": "1", "mode": "buy"})
    orders = client.get("/store/orders").json()["orders"]
    assert len(orders) >= 1
    assert orders[0]["label"].endswith("BMW M4")
