"""Bulk-load cleaned car data (NDJSON) into Elasticsearch.

Owner: Kangjie.

Pipeline:  data/data.csv --(search.clean_data)--> data/cars_clean.json --(this)--> ES `cars`

Usage (run from the repo root):
    python -m search.clean_data    # produce data/cars_clean.json first
    python -m search.ingest        # then index it
"""
import json
from pathlib import Path

from elasticsearch import helpers

from backend.app.config import settings
from backend.app.es_client import get_es
from .index_mapping import CARS_MAPPING

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "cars_clean.json"


def _rows(path: Path):
    with path.open() as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if line:
                # store the row index as a real `id` field too, so the query layer
                # can sort on it (the metadata _id field isn't sortable in ES 8.x).
                yield {"_index": settings.es_index, "_id": str(i),
                       "_source": {**json.loads(line), "id": i}}


def main():
    if not DATA_PATH.exists():
        raise SystemExit(f"Missing {DATA_PATH}. Run `python -m search.clean_data` first.")

    es = get_es()
    if es.indices.exists(index=settings.es_index):
        es.indices.delete(index=settings.es_index)
    es.indices.create(index=settings.es_index, body=CARS_MAPPING)

    ok, _ = helpers.bulk(es, _rows(DATA_PATH))
    es.indices.refresh(index=settings.es_index)
    print(f"Indexed {ok} cars into '{settings.es_index}'.")


if __name__ == "__main__":
    main()
