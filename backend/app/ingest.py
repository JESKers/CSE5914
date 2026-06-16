"""Load the Kaggle car dataset into Elasticsearch.

Owner: Kangjie.

Usage:
    1. Download data.csv from
       https://www.kaggle.com/datasets/CooperUnion/cardataset
       and place it at backend/data/data.csv
    2. python -m app.ingest            # uses ES_HOST / ES_INDEX from env

Run from the `backend/` directory.
"""
import math
from pathlib import Path

import pandas as pd
from elasticsearch import helpers

from .config import settings
from .es_client import get_es
from .index_mapping import CARS_MAPPING

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "data.csv"

# Kaggle column -> our field name
COLUMN_MAP = {
    "Make": "make",
    "Model": "model",
    "Year": "year",
    "Engine Fuel Type": "engine_fuel_type",
    "Engine HP": "engine_hp",
    "Engine Cylinders": "engine_cylinders",
    "Transmission Type": "transmission_type",
    "Driven_Wheels": "driven_wheels",
    "Number of Doors": "number_of_doors",
    "Market Category": "market_category",
    "Vehicle Size": "vehicle_size",
    "Vehicle Style": "vehicle_style",
    "highway MPG": "highway_mpg",
    "city mpg": "city_mpg",
    "Popularity": "popularity",
    "MSRP": "msrp",
}


def _clean(value):
    """Drop NaNs so ES doesn't choke on missing numerics."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _rows(df: pd.DataFrame):
    for i, row in df.iterrows():
        doc = {field: _clean(row[col]) for col, field in COLUMN_MAP.items()}
        # combined free-text field for the keyword box
        doc["text"] = " ".join(
            str(doc[f]) for f in ("make", "model", "market_category", "vehicle_style")
            if doc.get(f) is not None
        )
        doc = {k: v for k, v in doc.items() if v is not None}
        yield {"_index": settings.es_index, "_id": str(i), "_source": doc}


def main():
    if not DATA_PATH.exists():
        raise SystemExit(
            f"Missing dataset at {DATA_PATH}. Download data.csv from Kaggle first."
        )

    es = get_es()
    if es.indices.exists(index=settings.es_index):
        es.indices.delete(index=settings.es_index)
    es.indices.create(index=settings.es_index, body=CARS_MAPPING)

    df = pd.read_csv(DATA_PATH)
    ok, _ = helpers.bulk(es, _rows(df))
    es.indices.refresh(index=settings.es_index)
    print(f"Indexed {ok} cars into '{settings.es_index}'.")


if __name__ == "__main__":
    main()
