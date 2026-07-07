#!/usr/bin/env python3
"""Simple demo script for showing the RAG + Elasticsearch integration.

Demo-specific entrypoint: this script is intended for live presentation runs.
Run inside the backend container:
    docker compose exec backend python3 /app/demo_rag_es.py
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
from backend.app.schemas import SearchFilters


def ensure_data_ready():
    # Demo-specific: prepare the dataset and Elasticsearch index before running the demo.
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)

    csv_path = data_dir / "data.csv"
    if not csv_path.exists():
        print(f"No dataset found at {csv_path}. Put your CSV there first.")
        sys.exit(1)

    cleaned_path = data_dir / "cars_clean.json"
    print("Cleaning CSV into NDJSON...")
    df = clean(csv_path)
    to_ndjson(df, cleaned_path)

    es = get_es()
    if es.indices.exists(index=settings.es_index):
        print(f"Deleting existing index '{settings.es_index}'...")
        es.indices.delete(index=settings.es_index)

    print("Ingesting cleaned data into Elasticsearch...")
    ingest_main()


def main():
    # Demo-specific: run a few example queries to show the end-to-end RAG flow.
    ensure_data_ready()

    queries = [
        "cheap fuel efficient sedan",
        "luxury SUV with high horsepower",
        "affordable sporty coupe",
    ]

    print("\nRAG + Elasticsearch demo\n")
    for q in queries:
        print(f"Query: {q}")
        print("-" * 60)
        filters = SearchFilters(q=q, page=1, size=3)
        search_results = search_service.search(filters)
        print(f"Elasticsearch matches: {search_results['total']}")
        for result in search_results['results'][:3]:
            print(f"  - {result.get('year')} {result.get('make')} {result.get('model')} | MSRP ${result.get('msrp')}")
        print("Demo summary:")
        print(f"  Retrieved {search_results['total']} Elasticsearch matches for '{q}'.")
        print("  This demonstrates the ES-backed retrieval layer for the RAG demo.")
        print()


if __name__ == "__main__":
    main()
