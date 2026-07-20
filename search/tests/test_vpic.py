from search import vpic


def test_model_evidence_matches_normalized_model_name(monkeypatch):
    monkeypatch.setattr(vpic, "_evidence_cache_get", lambda key: None)
    monkeypatch.setattr(vpic, "_evidence_cache_set", lambda key, value: None)
    monkeypatch.setattr(vpic, "_get", lambda path: {"Results": [{
        "Make_ID": 452, "Model_ID": 1861, "Model_Name": "MX-5 Miata",
        "VehicleTypeName": "PASSENGER CAR",
    }]})

    evidence = vpic.model_evidence("Mazda", "MX 5 Miata", 2016)

    assert evidence["status"] == "verified"
    assert evidence["model_id"] == 1861


def test_model_evidence_distinguishes_old_year_and_api_failure(monkeypatch):
    assert vpic.model_evidence("BMW", "M3", 1995)["status"] == "not_supported"
    monkeypatch.setattr(vpic, "_evidence_cache_get", lambda key: None)
    monkeypatch.setattr(vpic, "_get", lambda path: {"_error": True, "Results": []})
    assert vpic.model_evidence("BMW", "M3", 2015)["status"] == "unavailable"


def test_vpic_evidence_cache_persists_between_memory_resets(monkeypatch, tmp_path):
    cache_path = tmp_path / "evidence.json"
    monkeypatch.setattr(vpic, "EVIDENCE_CACHE_PATH", cache_path)
    monkeypatch.setattr(vpic, "_evidence_cache", {})
    vpic._evidence_cache_set("bmw|m4|2016", {"status": "verified", "verified": True})
    monkeypatch.setattr(vpic, "_evidence_cache", None)

    cached = vpic._evidence_cache_get("bmw|m4|2016")
    assert cached["verified"] is True
    assert cached["cache_hit"] is True
