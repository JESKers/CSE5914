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
# The demo dataset lives next to this file, so the fallback path can still work offline.
DATASET = Path(__file__).resolve().parent / "data_small.csv"
# FAISS needs a place to persist its index between runs.
INDEX_DIR = Path(__file__).resolve().parent / "faiss_index"

if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from backend.app.schemas import SearchFilters  # noqa: E402
from search import search_service  # noqa: E402

try:
    from .parser import parse_query, detect_intents
except ImportError:  # pragma: no cover - allows direct script execution
    from parser import parse_query, detect_intents

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
    # If the demo file is present, this gives the fallback path something concrete to work with.
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


def build_fallback_answer(query: str, docs: List[dict], top_k: int = 5) -> str:
    if not docs:
        return (
            f"I could not reach the local LLM service for '{query}', and no Elasticsearch matches were available."
        )

    preview = docs[:top_k]
    summary = format_docs(preview)
    return (
        f"I could not reach the local LLM service for '{query}', so here are the top Elasticsearch matches instead:\n"
        f"{summary}"
    )


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _get_text(car: dict, key: str) -> str:
    return str(car.get(key, "") or "").lower()


SPORTY_MODEL_WORDS = [
    "mustang", "camaro", "challenger", "corvette", "370z", "brz", "fr-s",
    "frs", "86", "genesis coupe", "boxster", "cayman", "tt", "z4",
]

LUXURY_MAKES = [
    "bmw", "mercedes-benz", "audi", "lexus", "cadillac", "infiniti",
    "acura", "porsche", "lincoln", "volvo",
]


def _matches_body_intent(intents: dict, car: dict) -> bool:
    style = _get_text(car, "vehicle_style")
    model = _get_text(car, "model")

    if not intents["body_styles"]:
        return True

    for body_style in intents["body_styles"]:
        if body_style == "truck":
            if "truck" in style or "pickup" in style:
                return True
        elif body_style == "coupe":
            if "coupe" in style or "coupe" in model:
                return True
        elif body_style in style:
            return True

    return False


def _rank_car_for_query(intents: dict, car: dict) -> float:
    style = _get_text(car, "vehicle_style")
    model = _get_text(car, "model")
    make = _get_text(car, "make")
    transmission = _get_text(car, "transmission_type")
    fuel = _get_text(car, "engine_fuel_type")

    hp = _safe_float(car.get("engine_hp"))
    msrp = _safe_float(car.get("msrp"), default=999999.0)
    city_mpg = _safe_float(car.get("city_mpg"))
    highway_mpg = _safe_float(car.get("highway_mpg"))

    score = 0.0

    for body_style in intents["body_styles"]:
        if body_style == "truck":
            matches = "truck" in style or "pickup" in style
        elif body_style == "coupe":
            matches = "coupe" in style or "coupe" in model
        else:
            matches = body_style in style
        score += 5000 if matches else -5000

    if intents["sport"]:
        score += hp * 3
        full_name = f"{make} {model}"
        if any(word in full_name for word in SPORTY_MODEL_WORDS):
            score += 1500

    if intents["affordable"]:
        score -= msrp / 20

    if intents["fuel_efficient"]:
        score += city_mpg * 80
        score += highway_mpg * 50
        score -= msrp / 100

    if intents["manual"]:
        score += 1500 if "manual" in transmission else -1000

    if intents["luxury"] and make in LUXURY_MAKES:
        score += 1500

    if intents["electric"] and "electric" in fuel:
        score += 1500

    return score


def _dedupe_results(results: list[dict]) -> list[dict]:
    seen = set()
    deduped = []

    for car in results:
        key = (
            car.get("year"),
            car.get("make"),
            car.get("model"),
            car.get("msrp"),
            car.get("engine_hp"),
            car.get("vehicle_style"),
        )

        if key in seen:
            continue

        seen.add(key)
        deduped.append(car)

    return deduped


def _extra_queries_for_intent(intents: dict) -> list[str]:
    extra_queries = []

    if "coupe" in intents["body_styles"]:
        extra_queries.extend([
            "coupe",
            "sport coupe",
            "performance coupe",
            "manual coupe",
            "mustang camaro challenger coupe",
        ])

    if "suv" in intents["body_styles"]:
        extra_queries.extend([
            "suv",
            "luxury suv",
            "premium suv",
            "horsepower suv",
        ])

    if intents["fuel_efficient"]:
        extra_queries.extend([
            "fuel efficient",
            "high mpg",
            "commuter",
            "hybrid",
        ])

    return extra_queries


def retrieve_es_documents(query: str, top_k: int = 5) -> dict:
    pool_size = max(top_k * 50, 100)
    all_results = []
    intents = detect_intents(query)

    try:
        filters = parse_query(query)
        filters.page = 1
        filters.size = pool_size
        if os.getenv("DEBUG_RAG", "false").lower() == "true":
            print("PARSED FILTERS:", filters.model_dump(exclude_none=True))

        no_structured_filters = not any([
            filters.make, filters.model, filters.year_min, filters.year_max,
            filters.price_min, filters.price_max, filters.hp_min, filters.hp_max,
            filters.engine_fuel_type, filters.transmission_type,
        ])
        if no_structured_filters and not filters.q:
            filters.q = query
    except Exception as exc:
        if os.getenv("DEBUG_RAG", "false").lower() == "true":
            print("PARSE FAILED:", exc)
        filters = SearchFilters(q=query, page=1, size=pool_size)

    search_results = search_service.search(filters)
    all_results.extend(search_results.get("results", []))

    for extra_query in _extra_queries_for_intent(intents):
        try:
            extra_filters = SearchFilters(q=extra_query, page=1, size=pool_size)
            extra_results = search_service.search(extra_filters)
            all_results.extend(extra_results.get("results", []))
        except Exception:
            pass

    all_results = _dedupe_results(all_results)

    body_matches = [
        car for car in all_results
        if _matches_body_intent(intents, car)
    ]

    candidates = body_matches if body_matches else all_results

    ranked_results = sorted(
        candidates,
        key=lambda car: _rank_car_for_query(intents, car),
        reverse=True,
    )

    final_results = ranked_results[:top_k]

    return {
        **search_results,
        "total": len(final_results),
        "results": final_results,
    }

def recommend(query: str, rebuild: bool = False, top_k: int = 5):
    """Answer a free-text question using Elasticsearch results as retrieval context."""
    search_results = None

    # The first try uses the search index as context, which is the cleaner path for this demo.
    try:
        search_results = retrieve_es_documents(query, top_k=top_k)
        if not search_results["results"]:
            return "I found no matching cars in Elasticsearch for that query."

        context = format_docs(search_results["results"])
        if os.getenv("DEBUG_RAG", "false").lower() == "true":
            print("\nRAG CONTEXT:")
            print(context)
            print()
        prompt = PROMPT_TEMPLATE.format(context=context, question=query)
        llm = get_chat_model()
        response = llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)
    except Exception:
        if search_results is not None and search_results.get("results"):
            return build_fallback_answer(query, search_results["results"], top_k=top_k)

        if rebuild or not index_exists():
            try:
                store = build_demo_index()
                docs = store.similarity_search(query, k=top_k)
                context = "\n\n".join(doc.page_content for doc in docs)
                prompt = PROMPT_TEMPLATE.format(context=context, question=query)
                llm = get_chat_model()
                response = llm.invoke(prompt)
                return response.content if hasattr(response, "content") else str(response)
            except Exception:
                return build_fallback_answer(query, [], top_k=top_k)

        return build_fallback_answer(query, [], top_k=top_k)


if __name__ == "__main__":
    query = os.getenv("QUERY", "What is the difference between the skittles flavors?")
    print(recommend(query, rebuild=os.getenv("REBUILD_INDEX", "false").lower() == "true"))
