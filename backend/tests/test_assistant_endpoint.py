"""Tests for the AI buy/rent assistant — no live ES or Anthropic required.

The search core is monkeypatched (as in test_store_endpoint.py) and the
Anthropic client is replaced with a scripted fake, so these cover: the tool
dispatch layer (quotes, TCO, rental inventory/date validation), the agentic
loop (tool_use -> tool_result -> final text), error surfacing, and the
/assistant/* endpoints. Run from the repo root:  pytest
"""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app import agent, main, store
from backend.app.config import settings

client = TestClient(main.app)

_SAMPLE_CAR = {
    "id": "1", "make": "BMW", "model": "M4", "year": 2016, "msrp": 60000.0,
    "engine_hp": 425, "engine_fuel_type": "premium unleaded (required)",
    "transmission_type": "MANUAL", "vehicle_style": "Coupe",
    "highway_mpg": 26, "city_mpg": 17,
}


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    """Temp ledger DB, stubbed search core + vPIC, fresh sessions."""
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "store.db")
    monkeypatch.setattr(
        agent.search_service, "search",
        lambda f: {"total": 1, "page": f.page, "size": f.size, "results": [dict(_SAMPLE_CAR)]},
    )
    monkeypatch.setattr(agent.search_service, "get_car", lambda vid: dict(_SAMPLE_CAR))
    monkeypatch.setattr(agent.vpic, "is_verified", lambda make: True)
    agent._SESSIONS.clear()


# --------------------------------------------------------------------------- #
# Tool layer (pure, offline)
# --------------------------------------------------------------------------- #
def test_quote_loan_with_explicit_price():
    payload, summary = agent._t_quote_loan({"price": 30000, "credit_score": 720})
    assert payload["monthly_payment"] > 0
    assert payload["total_of_payments"] > 30000 * 0.5
    assert "/mo" in summary


def test_quote_lease_and_tco_use_catalog_car():
    lease, _ = agent._t_quote_lease({"vehicle_id": "1", "credit_score": 700})
    assert lease["monthly_payment"] > 0

    tco, _ = agent._t_compare_tco({"vehicle_id": "1", "years": 5})
    assert set(tco["options"]) == {"buy_new", "buy_cpo", "lease"}
    assert tco["recommended"] in tco["options"]


def test_quote_rental_prices_days_and_addons():
    quote, _ = agent._t_quote_rental({
        "vehicle_id": "1", "location_id": "CMH-DT",
        "pickup": "2026-07-15", "dropoff": "2026-07-19",
        "addons": {"child_seat": 1}, "protection": ["cdw"],
    })
    assert quote["days"] == 4
    assert quote["total"] > quote["daily_rate"] * 4  # add-ons/insurance/tax on top
    items = {l["item"] for l in quote["line_items"]}
    assert "Child / Booster Seat" in items


def test_rental_inventory_shape_and_date_validation():
    payload, _ = agent._t_search_rental_inventory({
        "location_id": "CMH-DT", "pickup": "2026-07-15", "dropoff": "2026-07-19",
    })
    assert payload["days"] == 4
    assert isinstance(payload["units"], list)

    with pytest.raises(ValueError):
        agent._rental_days("2026-07-19", "2026-07-15")


def test_run_tool_surfaces_errors_instead_of_raising():
    result_json, summary, is_error = agent._run_tool("quote_lease", {"vehicle_id": "1", "term_months": "oops"})
    assert is_error
    assert "error" in json.loads(result_json)

    result_json, _, is_error = agent._run_tool("no_such_tool", {})
    assert is_error


# --------------------------------------------------------------------------- #
# Agentic loop with a scripted fake Anthropic client
# --------------------------------------------------------------------------- #
def _text(t):
    return SimpleNamespace(type="text", text=t)


def _tool_use(id_, name, args):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=args)


def _resp(stop_reason, content):
    return SimpleNamespace(stop_reason=stop_reason, content=content)


class _FakeAnthropic:
    scripted = []       # class-level: responses for the next chat() run
    last_calls = []

    def __init__(self, api_key=None):
        self.messages = self

    def create(self, **kwargs):
        _FakeAnthropic.last_calls.append(kwargs)
        return _FakeAnthropic.scripted.pop(0)


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setattr("anthropic.Anthropic", _FakeAnthropic)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    _FakeAnthropic.scripted = []
    _FakeAnthropic.last_calls = []
    return _FakeAnthropic


def test_chat_runs_tool_loop_to_completion(fake_llm):
    fake_llm.scripted = [
        _resp("tool_use", [_text("Let me price that."),
                           _tool_use("tu1", "quote_loan", {"price": 30000})]),
        _resp("end_turn", [_text("A $30k loan runs about $520/mo.")]),
    ]
    r = client.post("/assistant/chat", json={"message": "Finance a $30k car for me"})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"].startswith("A $30k loan")
    assert [e["tool"] for e in body["events"]] == ["quote_loan"]
    assert not body["events"][0]["is_error"]

    # server kept the conversation: user msg, assistant tool turn, results, final
    history = agent._SESSIONS[body["session_id"]]
    assert history[0] == {"role": "user", "content": "Finance a $30k car for me"}
    assert history[2]["content"][0]["type"] == "tool_result"

    # the loop passed tools + system prompt to the model
    assert any(t["name"] == "book_rental" for t in fake_llm.last_calls[0]["tools"])
    assert "RENTAL" in fake_llm.last_calls[0]["system"]


def test_chat_reuses_session_and_reset_clears_it(fake_llm):
    fake_llm.scripted = [_resp("end_turn", [_text("Hi! Rent or buy?")])]
    first = client.post("/assistant/chat", json={"message": "hello"}).json()

    fake_llm.scripted = [_resp("end_turn", [_text("Great, which city?")])]
    second = client.post(
        "/assistant/chat", json={"message": "rent", "session_id": first["session_id"]}
    ).json()
    assert second["session_id"] == first["session_id"]
    assert len(agent._SESSIONS[first["session_id"]]) == 4  # 2 user + 2 assistant turns

    client.delete(f"/assistant/chat/{first['session_id']}")
    assert first["session_id"] not in agent._SESSIONS


def test_chat_tool_error_reaches_model_not_500(fake_llm):
    fake_llm.scripted = [
        _resp("tool_use", [_tool_use("tu1", "quote_rental", {
            "vehicle_id": "1", "location_id": "CMH-DT",
            "pickup": "2026-07-19", "dropoff": "2026-07-15",  # inverted dates
        })]),
        _resp("end_turn", [_text("Those dates look reversed — did you mean 15th to 19th?")]),
    ]
    r = client.post("/assistant/chat", json={"message": "rent something"})
    assert r.status_code == 200
    assert r.json()["events"][0]["is_error"] is True


def test_chat_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    r = client.post("/assistant/chat", json={"message": "hi"})
    assert r.status_code == 503


# --------------------------------------------------------------------------- #
# Bookings endpoint (demo verification surface)
# --------------------------------------------------------------------------- #
def test_bookings_endpoint_lists_agent_bookings():
    booking, _ = agent._t_book_rental({
        "vehicle_id": "1", "location_id": "CMH-DT",
        "pickup": "2026-07-15", "dropoff": "2026-07-19",
        "protection": ["cdw"], "customer": "Kangjie",
    })
    assert booking["confirmation"].startswith("RENT-")

    r = client.get("/assistant/bookings")
    assert r.status_code == 200
    body = r.json()
    assert len(body["rentals"]) == 1
    assert body["rentals"][0]["confirmation"] == booking["confirmation"]
    assert body["test_drives"] == []
