"""Tests for the AI buy/rent assistant — no live ES or Anthropic required.

The search core is monkeypatched (as in test_store_endpoint.py) and the
Anthropic client is replaced with a scripted fake, so these cover: the tool
dispatch layer (quotes, TCO, rental inventory/date validation), the agentic
loop (tool_use -> tool_result -> final text), error surfacing, and the
/assistant/* endpoints. Run from the repo root:  pytest
"""
import json
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app import agent, images, main, store, synth
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
    # keep image lookups offline: warm in-memory cache, cache file in tmp
    monkeypatch.setattr(images, "CACHE_PATH", tmp_path / "vehicle_images.json")
    monkeypatch.setattr(images, "_cache", {"bmw m4": "https://img.example/m4.jpg"})
    agent._SESSIONS.clear()
    agent._OLLAMA_SESSIONS.clear()
    agent._OLLAMA_SHOP_FILTERS.clear()
    agent._OLLAMA_SHOP_PAGES.clear()
    agent._OLLAMA_SHOP_COUNTS.clear()


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


def test_unit_identity_is_deterministic_and_plate_shaped():
    a = synth.unit_identity("CMH-DT", "1")
    b = synth.unit_identity("CMH-DT", "1")
    assert a == b  # same unit -> same plate/color/odometer every time
    assert a["plate"].startswith("OH ") and "-" in a["plate"]
    assert a["color"] in synth._UNIT_COLORS
    assert 8000 <= a["odometer_miles"] < 60000
    assert synth.unit_identity("CMH-AIR", "1")["plate"] != a["plate"]


def test_location_resolution_is_lenient():
    assert agent._location("cmh-dt")["id"] == "CMH-DT"          # case-insensitive
    assert agent._location("columbus-downtown")["city"] == "Columbus"  # city fallback
    with pytest.raises(ValueError, match="Valid ids"):
        agent._location("mars-base")


def test_listing_and_search_carry_image_url():
    listing, _ = agent._t_get_listing({"vehicle_id": "1"})
    assert listing["image_url"] == "https://img.example/m4.jpg"
    payload, _ = agent._t_search_cars({"make": "BMW"})
    assert payload["results"][0]["image_url"] == "https://img.example/m4.jpg"


def test_image_cache_hit_needs_no_network(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("network should not be touched on cache hit")
    monkeypatch.setattr(images.httpx, "get", _boom)
    assert images.image_for("BMW", "M4") == "https://img.example/m4.jpg"
    # transient network failure -> None, and the miss is NOT cached
    monkeypatch.setattr(images.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    assert images.image_for("Honda", "Pilot") is None
    assert "honda pilot" not in images._cache


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


def test_chat_uses_ollama_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(
        agent,
        "_chat_ollama",
        lambda session_id, message: {
            "reply": f"Local reply: {message}",
            "events": [],
        },
    )
    r = client.post("/assistant/chat", json={"message": "hi"})
    assert r.status_code == 200
    assert r.json()["reply"] == "Local reply: hi"


def test_ollama_general_chat_omits_tools(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"role": "assistant", "content": "I can help with cars."}}

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(agent.requests, "post", fake_post)
    result = agent._chat_ollama("local-session", "Hello, what can you do?")

    assert result["reply"] == "I can help with cars."
    assert "tools" not in calls[0][1]["json"]
    assert calls[0][1]["json"]["think"] is False


def test_ollama_selects_only_relevant_tools():
    rental_history = [{"role": "user", "content": "Rent an SUV this weekend"}]
    mode = agent._ollama_mode(rental_history)
    names = {tool["function"]["name"] for tool in agent._ollama_tools(mode)}

    assert mode == "rental"
    assert "search_rental_inventory" in names
    assert "book_rental" in names
    assert "place_purchase_order" not in names


def test_ollama_latest_explicit_mode_can_switch_journeys():
    history = [
        {"role": "user", "content": "I need a rental next week"},
        {"role": "assistant", "content": "Which city?"},
        {"role": "user", "content": "Actually I want to buy an SUV"},
    ]
    assert agent._ollama_mode(history) == "buy"


def test_grounded_shop_reply_uses_search_results():
    reply, result = agent._grounded_shop_reply("Find a BMW coupe")

    assert result["total"] == 1
    assert "2016 BMW M4" in reply
    assert "$60,000" in reply
    assert "**I understood:**" in reply


def test_grounded_shop_reply_shows_more_results_and_honors_count(monkeypatch):
    cars = [
        {**_SAMPLE_CAR, "id": str(index), "model": f"M4-{index}"}
        for index in range(20)
    ]
    monkeypatch.setattr(
        agent.search_service,
        "search",
        lambda filters: {
            "total": 100,
            "page": filters.page,
            "size": filters.size,
            "results": cars,
        },
    )

    default_reply, _ = agent._grounded_shop_reply("Find a BMW coupe")
    requested_reply, _ = agent._grounded_shop_reply("Show me 18 BMW cars")
    more_reply, _ = agent._grounded_shop_reply("I want to see much more")

    assert default_reply.count("| 2016 BMW M4-") == 12
    assert "with **12** different models" in default_reply
    assert requested_reply.count("| 2016 BMW M4-") == 18
    assert more_reply.count("| 2016 BMW M4-") == 20


def test_grounded_shop_results_are_diversified_by_model(monkeypatch):
    cars = [
        {**_SAMPLE_CAR, "id": "1", "model": "RAV4", "year": 2015},
        {**_SAMPLE_CAR, "id": "2", "model": "RAV4", "year": 2016},
        {**_SAMPLE_CAR, "id": "3", "model": "Highlander", "year": 2016},
    ]
    monkeypatch.setattr(
        agent.search_service,
        "search",
        lambda filters: {
            "total": 3, "page": 1, "size": filters.size, "results": cars,
        },
    )

    reply, result = agent._grounded_shop_reply("Find Toyota SUVs")

    assert reply.count("RAV4") == 1
    assert "Highlander" in reply
    assert result["diverse_total"] == 2


def test_grounded_shop_next_and_previous_pages(monkeypatch):
    cars = [
        {**_SAMPLE_CAR, "id": str(index), "model": f"Model-{index}"}
        for index in range(30)
    ]
    monkeypatch.setattr(
        agent.search_service,
        "search",
        lambda filters: {
            "total": 30, "page": 1, "size": filters.size, "results": cars,
        },
    )

    _, first = agent._grounded_shop_reply(
        "Find BMW cars",
        session_id="pages",
    )
    next_reply, second = agent._grounded_shop_reply(
        "Show the next page",
        session_id="pages",
    )
    _, previous = agent._grounded_shop_reply(
        "Go back",
        session_id="pages",
    )

    assert first["display_page"] == 1
    assert second["display_page"] == 2
    assert second["displayed_results"][0]["model"] == "Model-12"
    assert "page **2 of 3**" in next_reply
    assert previous["display_page"] == 1


def test_grounded_shop_can_remove_remembered_constraints(monkeypatch):
    seen = []

    def capture(filters):
        seen.append(filters)
        return {"total": 1, "page": 1, "size": filters.size, "results": [dict(_SAMPLE_CAR)]}

    monkeypatch.setattr(agent.search_service, "search", capture)
    agent._grounded_shop_reply(
        "Find a BMW coupe under $70000",
        session_id="remove-filters",
    )
    reply, result = agent._grounded_shop_reply(
        "Any brand is fine and remove the budget",
        session_id="remove-filters",
    )

    applied = agent._OLLAMA_SHOP_FILTERS["remove-filters"]
    assert applied.make is None
    assert applied.price_max is None
    assert applied.vehicle_styles == ["Coupe"]
    assert "removed budget, make" in reply
    assert "price_max" not in result["query_echo"]


def test_vehicle_age_request_reports_catalog_mismatch(monkeypatch):
    monkeypatch.setattr(
        agent.search_service,
        "search",
        lambda filters: {
            "total": 0, "page": 1, "size": filters.size, "results": [],
        },
    )

    reply, result = agent._grounded_shop_reply("Find an SUV at most 3 years old")

    assert result["query_echo"]["year_min"] == date.today().year - 3
    assert "catalog covers model years" in reply.casefold()


def test_grounded_shop_followup_remembers_and_refines_filters(monkeypatch):
    seen = []

    def capture(filters):
        seen.append(filters)
        return {"total": 1, "page": 1, "size": 20, "results": [dict(_SAMPLE_CAR)]}

    monkeypatch.setattr(agent.search_service, "search", capture)
    agent._grounded_shop_reply(
        "Find a BMW coupe under $70000",
        session_id="remember-me",
    )
    reply, result = agent._grounded_shop_reply(
        "Show me the cheaper ones",
        session_id="remember-me",
    )

    refined = seen[-1]
    assert refined.make.casefold() == "bmw"
    assert refined.vehicle_styles == ["Coupe"]
    assert refined.price_max == 70000
    assert refined.sort == "price"
    assert refined.order == "asc"
    assert refined.q is None
    assert result["query_echo"]["make"].casefold() == "bmw"
    assert "budget: up to $70,000" in reply


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
