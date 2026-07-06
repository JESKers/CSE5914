# RAG / LLM Spike (Owner: Jerry)

De-risking prototype for the **Timebox 3** Smart Car Recommendation System.
Proves the LLM + vector-store pieces work before the full RAG build.

> The legacy `ragllm` demo has been merged into this `rag` package. The Docker service now builds from `./rag`.

## Setup

```bash
cd rag
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama serve
ollama pull llama3.2
ollama pull nomic-embed-text
```

## 1. Confirm local LLM access
```bash
python hello_llm.py
```

## 2. Run the local RAG demo
```bash
python main.py
```

This demo will now use Elasticsearch to retrieve matching car documents and Ollama `llama3.2` for answer generation.

## 3. Build the vector store
Needs `backend/data/cars_clean.json` (Kangjie's cleaned NDJSON) — run
`python -m search.clean_data` from the repo root first.
```bash
python build_index.py "fuel-efficient SUV"
```

## 4. Test queries
[test_queries.md](test_queries.md) — the natural-language queries the system must
handle, with expected structured-filter outputs, for evaluating the NL parser.

## How this feeds Timebox 3
- `hello_llm.py` → local Ollama smoke test for the model layer
- `build_index.py` → embedding + retrieval layer for semantic recommendation
- `main.py` → simple local RAG entry point without API keys
- `test_queries.md` → the eval set that scores parser + retrieval quality
