"""Clean the Kaggle car dataset into NDJSON for Elasticsearch.

Owner: Kangjie (Elasticsearch).

Pipeline:
  1. normalize column names -> snake_case (matches backend.app.schemas / index_mapping)
  2. cast Year / Engine HP / MSRP (+ MPG, cylinders) to numeric
  3. impute nulls in Engine HP and MPG (median by Make, global fallback)
  4. drop duplicate rows
  5. build a combined `text` field for the keyword search box
  6. write data/cars_clean.json as NDJSON (one car per line)

Usage (run from the repo root):
    python -m search.clean_data
    python -m search.clean_data --input data/data.csv --output data/cars_clean.json
"""
import argparse
import json
import re
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_INPUT = DATA_DIR / "data.csv"
DEFAULT_OUTPUT = DATA_DIR / "cars_clean.json"

# Accept both the legacy Kaggle-style headers and the Craigslist-style headers
# that are present in the repo's current data file.
COLUMN_ALIASES = {
    "make": ["Make", "make", "Manufacturer", "manufacturer"],
    "model": ["Model", "model"],
    "year": ["Year", "year"],
    "engine_fuel_type": ["Engine Fuel Type", "Engine Fuel Type ", "fuel"],
    "engine_hp": ["Engine HP", "engine_hp"],
    "engine_cylinders": ["Engine Cylinders", "cylinders"],
    "transmission_type": ["Transmission Type", "transmission"],
    "driven_wheels": ["Driven_Wheels", "drive"],
    "number_of_doors": ["Number of Doors", "Number of Doors "],
    "market_category": ["Market Category"],
    "vehicle_size": ["Vehicle Size", "size"],
    "vehicle_style": ["Vehicle Style", "type"],
    "highway_mpg": ["highway MPG"],
    "city_mpg": ["city mpg"],
    "popularity": ["Popularity", "popularity"],
    "msrp": ["MSRP", "price"],
}

NUMERIC_INT = ["year", "engine_cylinders", "number_of_doors", "highway_mpg",
               "city_mpg", "popularity"]
IMPUTE_COLS = ["engine_hp", "highway_mpg", "city_mpg"]  # Engine HP + MPG per spec


def _impute_by_make(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Fill nulls with the per-Make median, falling back to the global median."""
    make_median = df.groupby("make")[col].transform("median")
    df[col] = df[col].fillna(make_median).fillna(df[col].median())
    return df


def _infer_make_model_from_url(row: pd.Series) -> pd.Series:
    """Infer missing make/model values from common Craigslist URL patterns."""
    if pd.isna(row.get("make")) or pd.isna(row.get("model")):
        url = str(row.get("url", "") or "")
        if url:
            parts = url.rstrip("/").split("/")
            if len(parts) >= 2:
                candidate = parts[-2]
                segments = candidate.split("-")
                # Remove empty pieces and year token
                segments = [seg for seg in segments if seg]
                if segments and re.match(r"^\d{4}$", segments[0]):
                    segments = segments[1:]
                if len(segments) >= 2:
                    make_candidate = segments[0].title()
                    model_candidate = " ".join(seg.title() for seg in segments[1:])
                    if pd.isna(row.get("make")) and make_candidate:
                        row["make"] = make_candidate
                    if pd.isna(row.get("model")) and model_candidate:
                        row["model"] = model_candidate
    return row


def clean(input_path: Path) -> pd.DataFrame:
    df = pd.read_csv(input_path)

    # 1. normalize columns to the schema expected by ES and the API
    renamed = {}
    for target, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in df.columns:
                renamed[alias] = target
                break
    df = df.rename(columns=renamed)

    # The repo's current file uses `manufacturer` and `model` values that are
    # not captured by the earlier Kaggle-style column names. Fill the normalized
    # fields from the exact raw columns present in this dataset.
    if "make" not in df.columns:
        df["make"] = df["manufacturer"] if "manufacturer" in df.columns else pd.NA
    if "model" not in df.columns:
        df["model"] = df["model"] if "model" in df.columns else pd.NA

    # Normalize blank strings to NA so URL-based inference can fill missing
    # make/model values correctly.
    if "make" in df.columns:
        df["make"] = df["make"].replace({"": pd.NA})
    if "model" in df.columns:
        df["model"] = df["model"].replace({"": pd.NA})

    # Infer make/model from the URL when the raw CSV fields are empty.
    if "url" in df.columns:
        df = df.apply(_infer_make_model_from_url, axis=1)

    # Fill in missing values for the common vehicle fields used by the demo.
    for col in ["engine_fuel_type", "transmission_type", "vehicle_style", "vehicle_size"]:
        if col not in df.columns:
            df[col] = pd.NA

    # If the raw file still has values under the original names, copy them over.
    for source, target in [("manufacturer", "make"), ("model", "model")]:
        if source in df.columns and target in df.columns:
            mask = df[target].isna()
            if mask.any():
                df.loc[mask, target] = df.loc[mask, source]

    # "N/A" market category -> real null
    if "market_category" in df.columns:
        df["market_category"] = df["market_category"].replace("N/A", pd.NA)

    # 2. numeric casts (coerce bad values to NaN first)
    for col in ["engine_hp", "msrp"] + NUMERIC_INT:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 3. impute Engine HP + MPG nulls
    for col in IMPUTE_COLS:
        if col in df.columns:
            df = _impute_by_make(df, col)

    # 4. dedupe identical listings
    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    print(f"Dropped {before - len(df)} duplicate rows ({before} -> {len(df)}).")

    # whole-number columns: cast to nullable Int after imputation
    for col in ["engine_hp"] + NUMERIC_INT:
        if col in df.columns:
            df[col] = df[col].round().astype("Int64")

    # 5. combined free-text field for keyword search
    text_parts = [c for c in ["make", "model", "market_category", "vehicle_style", "description", "url"] if c in df.columns]
    if text_parts:
        text_df = df[text_parts].copy()
        for col in text_df.columns:
            text_df[col] = text_df[col].fillna("").astype(str)
        df["text"] = (
            text_df.agg(" ".join, axis=1)
            .str.replace(r"\s+", " ", regex=True).str.strip()
        )
    else:
        df["text"] = ""

    return df


def to_ndjson(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as fh:
        for record in df.to_dict(orient="records"):
            doc = {k: (None if pd.isna(v) else v) for k, v in record.items()}
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
