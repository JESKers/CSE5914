"""Clean the Kaggle car dataset into NDJSON for Elasticsearch.

Owner: Kangjie (Elasticsearch).

Pipeline:
  1. normalize column names -> snake_case (matches app.schemas / index_mapping)
  2. cast Year / Engine HP / MSRP (+ MPG, cylinders) to numeric
  3. impute nulls in Engine HP and MPG (median by Make, global fallback)
  4. drop duplicate rows
  5. build a combined `text` field for the keyword search box
  6. write cars_clean.json as NDJSON (one car per line)

Usage (run from backend/):
    python -m app.clean_data
    python -m app.clean_data --input data/data.csv --output data/cars_clean.json

The output feeds the bulk loader (see app.ingest).
"""
import argparse
import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_INPUT = DATA_DIR / "data.csv"
DEFAULT_OUTPUT = DATA_DIR / "cars_clean.json"

# Raw Kaggle header -> snake_case field name
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

NUMERIC_INT = ["year", "engine_cylinders", "number_of_doors", "highway_mpg",
               "city_mpg", "popularity"]
IMPUTE_COLS = ["engine_hp", "highway_mpg", "city_mpg"]  # Engine HP + MPG per spec


def _impute_by_make(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Fill nulls with the per-Make median, falling back to the global median."""
    make_median = df.groupby("make")[col].transform("median")
    df[col] = df[col].fillna(make_median).fillna(df[col].median())
    return df


def clean(input_path: Path) -> pd.DataFrame:
    df = pd.read_csv(input_path)

    # 1. snake_case column names
    df = df.rename(columns=COLUMN_MAP)

    # "N/A" market category -> real null
    if "market_category" in df:
        df["market_category"] = df["market_category"].replace("N/A", pd.NA)

    # 2. numeric casts (coerce bad values to NaN first)
    for col in ["engine_hp", "msrp"] + NUMERIC_INT:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 3. impute Engine HP + MPG nulls
    for col in IMPUTE_COLS:
        if col in df:
            df = _impute_by_make(df, col)

    # 4. dedupe identical listings
    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    print(f"Dropped {before - len(df)} duplicate rows ({before} -> {len(df)}).")

    # whole-number columns: cast to nullable Int after imputation
    for col in ["engine_hp"] + NUMERIC_INT:
        if col in df:
            df[col] = df[col].round().astype("Int64")

    # 5. combined free-text field for keyword search
    parts = ["make", "model", "market_category", "vehicle_style"]
    df["text"] = (
        df[parts].fillna("").astype(str).agg(" ".join, axis=1)
        .str.replace(r"\s+", " ", regex=True).str.strip()
    )

    return df


def to_ndjson(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as fh:
        for record in df.to_dict(orient="records"):
            # drop nulls so ES docs stay clean
            doc = {
                k: (None if pd.isna(v) else v)
                for k, v in record.items()
            }
            doc = {k: v for k, v in doc.items() if v is not None}
            fh.write(json.dumps(doc) + "\n")
    print(f"Wrote {len(df)} cars -> {output_path}")


def main():
    ap = argparse.ArgumentParser(description="Clean Kaggle car data -> NDJSON")
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    if not args.input.exists():
        raise SystemExit(
            f"Missing {args.input}. Download data.csv from "
            "https://www.kaggle.com/datasets/CooperUnion/cardataset"
        )

    df = clean(args.input)
    to_ndjson(df, args.output)


if __name__ == "__main__":
    main()
