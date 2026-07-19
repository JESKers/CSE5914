"""Build a FAISS vector store over the car dataset using local Ollama embeddings.

This keeps the rag package fully local and avoids any API key requirement.
"""
import json
import sys
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

try:
    from .ollama_utils import get_embeddings
except ImportError:  # pragma: no cover - allows direct script execution
    from ollama_utils import get_embeddings

ROOT = Path(__file__).resolve().parent.parent
NDJSON = ROOT / "data" / "cars_clean.json"
INDEX_DIR = Path(__file__).resolve().parent / "faiss_index"


def _doc_text(car: dict) -> str:
    """Human-readable description the embedding model can match against."""
    bits = [
        str(car.get("year", "")),
        car.get("make", ""),
        car.get("model", ""),
        car.get("vehicle_style", ""),
        f'{car.get("engine_hp")}hp' if car.get("engine_hp") else "",
        car.get("engine_fuel_type", ""),
        car.get("transmission_type", ""),
        car.get("market_category", ""),
        f'${int(car["msrp"]):,}' if car.get("msrp") else "",
    ]
    return " ".join(b for b in bits if b).strip()


def load_cars():
    if not NDJSON.exists():
        raise SystemExit(
            f"Missing {NDJSON}. Run `python -m search.clean_data` from the repo root first."
        )
    with NDJSON.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def build():
    cars = load_cars()
    docs = [
        Document(page_content=_doc_text(c), metadata={"id": str(i), **c})
        for i, c in enumerate(cars)
    ]
    embeddings = get_embeddings()
    store = FAISS.from_documents(docs, embeddings)
    store.save_local(str(INDEX_DIR))
    print(f"Saved FAISS index -> {INDEX_DIR}")
    return store


def load_store():
    embeddings = get_embeddings()
    return FAISS.load_local(str(INDEX_DIR), embeddings, allow_dangerous_deserialization=True)


if __name__ == "__main__":
    store = build()
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"\nTop matches for: {query!r}")
        for doc in store.similarity_search(query, k=5):
            print(f"  - {doc.page_content}")
