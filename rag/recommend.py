"""Simple local Ollama-based RAG entry point for the rag package.

This intentionally avoids any API key and uses local models via Ollama.
It can work with a simple CSV/JSON dataset or later be connected to Elasticsearch.
"""
import os
import sys
from pathlib import Path
from typing import List

from langchain_community.vectorstores import FAISS

try:
    from .ollama_utils import get_chat_model, get_embeddings
except ImportError:  # pragma: no cover - allows direct script execution
    from ollama_utils import get_chat_model, get_embeddings

ROOT = Path(__file__).resolve().parent.parent
DATASET = Path(__file__).resolve().parent / "data_small.csv"
INDEX_DIR = Path(__file__).resolve().parent / "faiss_index"

if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from backend.app.schemas import SearchFilters  # noqa: E402
from search import search_service  # noqa: E402

PROMPT_TEMPLATE = """
Human: You are an AI assistant, and provide answers to questions using the provided car data.
Use the following pieces of information to provide a concise answer to the question enclosed in <question> tags.
If you don't know the answer, say that you don't know, don't try to make up an answer.
<context>
{context}
</context>

<question>
{question}
</question>

Assistant:"""


def index_exists() -> bool:
    return (INDEX_DIR / "index.faiss").exists() and (INDEX_DIR / "index.pkl").exists()


def build_demo_index():
    """Create a minimal FAISS index from the demo CSV if available."""
    if not DATASET.exists():
        raise FileNotFoundError(f"Dataset not found: {DATASET}")

    from langchain_community.document_loaders import CSVLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    loader = CSVLoader(file_path=str(DATASET))
    documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)
    docs = text_splitter.split_documents(documents)

    embeddings = get_embeddings()
    store = FAISS.from_documents(docs, embeddings)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    store.save_local(str(INDEX_DIR))
    return store


def load_index():
    embeddings = get_embeddings()
    return FAISS.load_local(str(INDEX_DIR), embeddings, allow_dangerous_deserialization=True)


def format_car(car: dict) -> str:
    lines = [
        f"{car.get('year', '?')} {car.get('make', '')} {car.get('model', '')}".strip(),
        f"Body: {car.get('vehicle_style')}" if car.get("vehicle_style") else None,
        f"Engine: {car.get('engine_hp')} hp {car.get('engine_fuel_type')}" if car.get("engine_hp") else None,
        f"Transmission: {car.get('transmission_type')}" if car.get("transmission_type") else None,
        f"MSRP: ${int(car['msrp']):,}" if car.get("msrp") else None,
        f"City MPG: {car.get('city_mpg')}" if car.get("city_mpg") else None,
        f"Highway MPG: {car.get('highway_mpg')}" if car.get("highway_mpg") else None,
    ]
    return "\n".join(line for line in lines if line)


def format_docs(docs: List[dict]) -> str:
    return "\n\n".join(format_car(doc) for doc in docs)


def retrieve_es_documents(query: str, top_k: int = 5) -> dict:
    filters = SearchFilters(q=query, page=1, size=top_k)
    return search_service.search(filters)


def recommend(query: str, rebuild: bool = False, top_k: int = 5):
    """Answer a free-text question using Elasticsearch results as retrieval context."""
    try:
        search_results = retrieve_es_documents(query, top_k=top_k)
        if not search_results["results"]:
            return "I found no matching cars in Elasticsearch for that query."

        context = format_docs(search_results["results"])
        prompt = PROMPT_TEMPLATE.format(context=context, question=query)
        llm = get_chat_model()
        response = llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)
    except Exception:
        if rebuild or not index_exists():
            store = build_demo_index()
            docs = store.similarity_search(query, k=top_k)
            context = "\n\n".join(doc.page_content for doc in docs)
            prompt = PROMPT_TEMPLATE.format(context=context, question=query)
            llm = get_chat_model()
            response = llm.invoke(prompt)
            return response.content if hasattr(response, "content") else str(response)
        raise


if __name__ == "__main__":
    query = os.getenv("QUERY", "What is the difference between the skittles flavors?")
    print(recommend(query, rebuild=os.getenv("REBUILD_INDEX", "false").lower() == "true"))
