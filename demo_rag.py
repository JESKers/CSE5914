#!/usr/bin/env python3
"""Simple demo script for showing the RAG + Elasticsearch integration.

Demo-specific entrypoint: this script is intended for live presentation runs.
Run inside the backend container:
    docker compose exec backend python3 /app/demo_rag.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from search.clean_data import clean, to_ndjson
from search.ingest import main as ingest_main
from backend.app.config import settings
from backend.app.es_client import get_es
from search import search_service
from rag.recommend import recommend, retrieve_es_documents

def build_fallback_answer(query: str, search_results: dict) -> str:
    results = search_results.get("results", [])[:3]
    if not results:
        return (
            f"I could not reach Elasticsearch for '{query}', so I do not have live car matches to recommend right now."
        )

    lines = []
    for result in results:
        year = result.get("year")
        make = result.get("make")
        model = result.get("model")
        msrp = result.get("msrp")
        fuel = result.get("engine_fuel_type")
        hp = result.get("engine_hp")
        detail_bits = [part for part in [year, make, model] if part]
        label = " ".join(map(str, detail_bits)) if detail_bits else "a matching car"
        extras = []
        if fuel:
            extras.append(fuel)
        if hp:
            extras.append(f"{hp} hp")
        extra_text = f" ({', '.join(extras)})" if extras else ""
        price_text = f" at ${msrp}" if msrp is not None else ""
        lines.append(f"- {label}{extra_text}{price_text}")

    return f"For '{query}', a practical starting point is:\n" + "\n".join(lines)


def ensure_data_ready(force: bool = False):
    # Demo-specific: prepare the dataset and Elasticsearch index before running the demo.
    # Cleaning + ingesting the full ~427k-row CSV takes several minutes, so by
    # default this is skipped once the cleaned file and ES index already exist.
    # Pass force=True (or set REBUILD_INDEX=true) to force a full rebuild.
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)

    csv_path = data_dir / "data.csv"
    if not csv_path.exists():
        print(f"No dataset found at {csv_path}. Put your CSV there first.")
        sys.exit(1)

    cleaned_path = data_dir / "cars_clean.json"
    needs_clean = force or not cleaned_path.exists() or (
        csv_path.stat().st_mtime > cleaned_path.stat().st_mtime
    )

    if needs_clean:
        print("Cleaning CSV into NDJSON...")
        df = clean(csv_path)
        to_ndjson(df, cleaned_path)
    else:
        print(f"Found up-to-date {cleaned_path}. Skipping clean_data.")

    try:
        es = get_es()
        index_exists = es.indices.exists(index=settings.es_index)

        if index_exists and not needs_clean and not force:
            print(f"Index '{settings.es_index}' already exists. Skipping ingest.")
            return

        if index_exists:
            print(f"Deleting existing index '{settings.es_index}'...")
            es.indices.delete(index=settings.es_index)

        print("Ingesting cleaned data into Elasticsearch...")
        ingest_main()
    except Exception as exc:
        print(f"Elasticsearch is not available ({exc}); continuing without index ingestion.")


def main():
    # Demo-specific: run a few example queries to show the end-to-end RAG flow.
    force_rebuild = os.getenv("REBUILD_INDEX", "false").lower() == "true"
    ensure_data_ready(force=force_rebuild)

    queries = [
        "Which affordable cars are good for fuel efficiency and daily commuting?",
        "Which luxury SUVs have strong horsepower and a premium feel?",
        "What sporty coupes offer a good balance of price and performance?",
        "What is some features of the 2017 dodge challenger?",
    ]

    print("\nRAG + Elasticsearch demo\n")
    for q in queries:
        print(f"Query: {q}")
        print("-" * 60)
        try:
            search_results = retrieve_es_documents(q, top_k=3)
            print(f"Elasticsearch matches: {search_results['total']}")
            for result in search_results['results'][:3]:
                print(
                    f"  - {result.get('year')} "
                    f"{result.get('make')} "
                    f"{result.get('model')} "
                    f"| Body {result.get('vehicle_style')} "
                    f"| HP {result.get('engine_hp')} "
                    f"| MSRP ${result.get('msrp')}"
                )
        except Exception as exc:
            search_results = {"results": []}
            print(f"Elasticsearch search unavailable: {exc}")

        print("RAG answer:")
        try:
            answer = recommend(q, rebuild=False, top_k=3)
            print(answer)
        except Exception as exc:
            print(build_fallback_answer(q, search_results))
            print(f"RAG response could not be generated: {exc}")

if __name__ == "__main__":
    main()
