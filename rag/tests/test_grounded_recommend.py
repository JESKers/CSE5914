from rag import grounded_recommend


CAR = {
    "id": "42", "make": "BMW", "model": "M4", "year": 2016,
    "msrp": 65000, "engine_hp": 425, "transmission_type": "MANUAL",
    "vehicle_style": "Coupe", "city_mpg": 17, "highway_mpg": 26,
}


def test_vpic_enrichment_is_bounded_and_preserves_es_rows(monkeypatch):
    calls = []
    monkeypatch.setattr(grounded_recommend.vpic, "model_evidence", lambda *args: (
        calls.append(args) or {"status": "verified", "verified": True}
    ))
    cars = [CAR, {**CAR, "id": "43"}, {**CAR, "id": "44", "model": "M3"}]

    enriched = grounded_recommend.enrich_with_vpic(cars, max_lookups=1)

    assert calls == [("BMW", "M4", 2016)]
    assert enriched[0]["vpic_evidence"]["status"] == "verified"
    assert enriched[1]["vpic_evidence"]["status"] == "verified"
    assert enriched[2]["vpic_evidence"]["status"] == "not_checked"
    assert enriched[0]["msrp"] == 65000


def test_llm_prompt_contains_only_retrieved_evidence(monkeypatch):
    captured = {}

    class FakeModel:
        def invoke(self, prompt):
            captured["prompt"] = prompt
            return type("Response", (), {"content": "Choose the M4 [car:42]."})()

    monkeypatch.setattr(grounded_recommend, "get_chat_model", lambda temperature=0: FakeModel())
    enriched = [{**CAR, "vpic_evidence": {"status": "verified", "vehicle_type": "PASSENGER CAR"}}]

    text, mode = grounded_recommend.generate_grounded_summary("manual BMW", enriched)

    assert mode == "langchain-ollama"
    assert text == "Choose the M4 [car:42]."
    assert "[car:42]" in captured["prompt"]
    assert "msrp=65000" in captured["prompt"]


def test_ollama_failure_returns_grounded_fallback(monkeypatch):
    class FailingModel:
        def invoke(self, prompt):
            raise ConnectionError("offline")

    monkeypatch.setattr(grounded_recommend, "get_chat_model", lambda temperature=0: FailingModel())
    text, mode = grounded_recommend.generate_grounded_summary("manual BMW", [CAR])

    assert mode == "deterministic"
    assert "[car:42]" in text


def test_uncited_or_unknown_llm_claim_is_replaced_with_fallback(monkeypatch):
    class HallucinatingModel:
        def invoke(self, prompt):
            return type("Response", (), {"content": "Choose an invented car [car:999]."})()

    monkeypatch.setattr(grounded_recommend, "get_chat_model", lambda temperature=0: HallucinatingModel())
    text, mode = grounded_recommend.generate_grounded_summary("manual BMW", [CAR])

    assert mode == "deterministic"
    assert "[car:42]" in text
    assert "999" not in text
