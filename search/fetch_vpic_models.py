"""Snapshot vPIC models for the makes that exist in our car catalog.

Owner: Kangjie (search core). Companion to search/vpic.py.

vPIC is a live query API with ~12k makes, most irrelevant to our Kaggle-derived
catalog. Rather than bulk-import all of it (infeasible — models require one call
per make, VIN decode is unbounded), this script fetches the model list for ONLY
the makes actually present in the `cars` index and writes a local snapshot to
data/vpic_models.json. The snapshot lets /vpic/models answer offline and instantly.

Usage (run from the repo root):
    python -m search.fetch_vpic_models                 # makes from ES, else fallback
    python -m search.fetch_vpic_models --make Honda --make BMW
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from . import vpic

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT_PATH = DATA_DIR / "vpic_models.json"

# Fallback make list (the 48 makes in the Kaggle car dataset) if ES is offline.
CATALOG_MAKES = [
    "Acura", "Alfa Romeo", "Aston Martin", "Audi", "BMW", "Bentley", "Bugatti",
    "Buick", "Cadillac", "Chevrolet", "Chrysler", "Dodge", "FIAT", "Ferrari",
    "Ford", "GMC", "Genesis", "HUMMER", "Honda", "Hyundai", "Infiniti", "Kia",
    "Lamborghini", "Land Rover", "Lexus", "Lincoln", "Lotus", "Maserati",
    "Maybach", "Mazda", "McLaren", "Mercedes-Benz", "Mitsubishi", "Nissan",
    "Oldsmobile", "Plymouth", "Pontiac", "Porsche", "Rolls-Royce", "Saab",
    "Scion", "Spyker", "Subaru", "Suzuki", "Tesla", "Toyota", "Volkswagen", "Volvo",
]


def catalog_makes() -> list[str]:
    """Distinct makes from the ES catalog, falling back to CATALOG_MAKES offline."""
    try:
        from search.search_service import facets
        makes = [b["key"] for b in facets()["makes"]]
        if makes:
            return sorted(makes)
    except Exception as exc:  # ES down / not ingested
        print(f"[warn] could not read makes from ES ({exc}); using bundled list.")
    return CATALOG_MAKES


def build_snapshot(makes: list[str]) -> dict:
    catalog: dict[str, dict] = {}
    total = 0
    for make in makes:
        rows = vpic.get_models_for_make(make)
        models = sorted({r["Model_Name"] for r in rows if r.get("Model_Name")})
        make_id = next((r.get("Make_ID") for r in rows if r.get("Make_ID")), None)
        catalog[make] = {"make_id": make_id, "models": models}
        total += len(models)
        print(f"  {make:15s} -> {len(models):4d} models")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "NHTSA vPIC GetModelsForMake",
        "make_count": len(catalog),
        "model_count": total,
        "makes": catalog,
    }


def main():
    ap = argparse.ArgumentParser(description="Snapshot vPIC models for catalog makes")
    ap.add_argument("--make", action="append", dest="makes",
                    help="restrict to specific make(s); repeatable")
    ap.add_argument("--output", type=Path, default=SNAPSHOT_PATH)
    args = ap.parse_args()

    makes = args.makes or catalog_makes()
    print(f"Fetching vPIC models for {len(makes)} make(s)...")
    snapshot = build_snapshot(makes)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2))
    print(f"Wrote {snapshot['model_count']} models across "
          f"{snapshot['make_count']} makes -> {args.output}")


if __name__ == "__main__":
    main()
