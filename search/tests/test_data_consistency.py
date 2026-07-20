import json
from pathlib import Path

from search.clean_data import clean, to_ndjson


def test_committed_clean_catalog_matches_source_csv(tmp_path):
    source = Path("data/data.csv")
    committed = Path("data/cars_clean.json")

    cleaned = clean(source)
    regenerated = tmp_path / "cars_clean.json"
    to_ndjson(cleaned, regenerated)

    expected = [json.loads(line) for line in committed.read_text(encoding="utf-8").splitlines()]
    actual = [json.loads(line) for line in regenerated.read_text(encoding="utf-8").splitlines()]
    assert len(expected) == 11199
    assert actual == expected
