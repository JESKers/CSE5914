"""Build a FAISS vector store over the car dataset for semantic recommendation.

Owner: Jerry (RAG/LLM). Timebox 3 prep.

Embeddings: local sentence-transformers model (all-MiniLM-L6-v2). The Anthropic
API has no embedding endpoint, so semantic vectors come from an open-source model
— no extra API key, runs offline. (For Timebox 3 we can compare this against
Voyage AI embeddings or Elasticsearch dense_vector.)

Usage (run from rag/):
    python build_index.py            # build rag/faiss_index from the car data
    python build_index.py "fast sports car under $50,000"   # build + demo query

Input: backend/data/cars_clean.json (Kangjie's NDJSON). Falls back to data.csv.
"""
import json
import sys
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

ROOT = Path(__file__).resolve().parent.parent
NDJSON = ROOT / "backend" / "data" / "cars_clean.json"
INDEX_DIR = Path(__file__).resolve().parent / "faiss_index"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


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
            f"Missing {NDJSON}. Run `python -m app.clean_data` in backend/ first."
        )
    with NDJSON.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def build():
    cars = load_cars()
    docs = [
        Document(page_content=_doc_text(c), metadata={"id": str(i), **c})
        for i, c in enumerate(cars)
    ]
    print(f"Embedding {len(docs)} cars with {EMBED_MODEL} ...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    store = FAISS.from_documents(docs, embeddings)
    store.save_local(str(INDEX_DIR))
    print(f"Saved FAISS index -> {INDEX_DIR}")
    return store


def load_store():
    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    return FAISS.load_local(str(INDEX_DIR), embeddings, allow_dangerous_deserialization=True)


if __name__ == "__main__":
    store = build()
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"\nTop matches for: {query!r}")
        for doc in store.similarity_search(query, k=5):
            print(f"  - {doc.page_content}")
