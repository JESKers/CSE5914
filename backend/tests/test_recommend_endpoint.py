"""Grounding tests for /recommend; Elasticsearch is replaced with canned rows."""
from fastapi.testclient import TestClient

from backend.app import main
from rag import grounded_recommend


client = TestClient(main.app)

_MATCH = {
    "id": "match", "make": "Ford", "model": "Mustang", "year": 2018,
    "msrp": 42000.0, "engine_hp": 460, "engine_fuel_type": "premium unleaded",
    "transmission_type": "MANUAL", "vehicle_style": "Coupe",
    "highway_mpg": 25, "city_mpg": 15,
}


class _FakeChatModel:
    def invoke(self, prompt):
        assert "[car:match]" in prompt
        return type("Response", (), {"content": (
            '{"summary":"The Mustang meets the request [car:match].",'
            '"recommended_vehicle_ids":["match"],"comparison_points":[]}'
        )})()


def _stub_grounding(monkeypatch):
    monkeypatch.setattr(grounded_recommend, "get_chat_model", lambda temperature=0: _FakeChatModel())
    monkeypatch.setattr(grounded_recommend.vpic, "model_evidence", lambda make, model, year: {
        "status": "verified", "verified": True, "model_id": 123,
        "vehicle_type": "PASSENGER CAR",
    })


def test_recommend_returns_grounded_reasons(monkeypatch):
    _stub_grounding(monkeypatch)
    captured = {}
    monkeypatch.setattr(main.search_service, "models", lambda make: ["Mustang"])

    def fake_search(filters):
        captured["filters"] = filters
        return {"results": [_MATCH], "total": 1, "page": 1, "size": 20}

    monkeypatch.setattr(main.search_service, "search", fake_search)
    response = client.post(
        "/recommend",
        json={"query": "manual Ford with at least 300 hp under $50k"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["id"] == "match"
    assert body["results"][0]["vpic_evidence"]["status"] == "verified"
    assert body["generation_mode"] == "langchain-ollama"
    assert body["narrative"].endswith("[car:match].")
    assert body["recommended_vehicle_ids"] == ["match"]
    assert any("300 hp minimum" in reason for reason in body["results"][0]["match_reasons"])
    assert captured["filters"].hp_min == 300
    assert captured["filters"].price_max == 50000
    assert captured["filters"].transmission_type == "MANUAL"


def test_recommend_drops_row_that_violates_hard_constraint(monkeypatch):
    _stub_grounding(monkeypatch)
    invalid = {**_MATCH, "id": "invalid", "msrp": 70000.0}
    monkeypatch.setattr(main.search_service, "models", lambda make: ["Mustang"])
    monkeypatch.setattr(
        main.search_service,
        "search",
        lambda filters: {"results": [invalid], "total": 1, "page": 1, "size": 20},
    )

    body = client.post("/recommend", json={"query": "Ford under $50k"}).json()
    assert body["results"] == []
    assert body["total"] == 0
    assert body["alternatives"][0]["relaxed_constraints"] == ["price_max"]
    assert body["message"].startswith("No exact matches")


def test_recommend_rejects_empty_or_oversized_query():
    assert client.post("/recommend", json={"query": ""}).status_code == 422
    assert client.post("/recommend", json={"query": "   "}).status_code == 422
    assert client.post("/recommend", json={"query": "x" * 501}).status_code == 422


def test_recommend_reports_contradictory_constraints(monkeypatch):
    monkeypatch.setattr(main.search_service, "models", lambda make: [])
    body = client.post(
        "/recommend", json={"query": "newer than 2020 but before 2010"}
    ).json()
    assert body["results"] == [] and body["alternatives"] == []
    assert "year minimum" in body["warnings"][0]


def test_recommend_labels_relaxed_alternatives(monkeypatch):
    _stub_grounding(monkeypatch)
    monkeypatch.setattr(main.search_service, "models", lambda make: ["Mustang"])

    def fake_search(filters):
        rows = [] if filters.price_max is not None else [{**_MATCH, "msrp": 52000.0}]
        return {"results": rows, "total": len(rows), "page": 1, "size": filters.size}

    monkeypatch.setattr(main.search_service, "search", fake_search)
    body = client.post("/recommend", json={"query": "Ford under $50k"}).json()
    assert body["results"] == []
    assert body["alternatives"][0]["relaxed_constraints"] == ["price_max"]
    assert "relaxed price_max" in body["warnings"][0]
