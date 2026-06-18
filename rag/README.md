# RAG / LLM Spike (Owner: Jerry)

De-risking prototype for the **Timebox 3** Smart Car Recommendation System.
Proves the LLM + vector-store pieces work before the full RAG build.

## Setup

```bash
cd rag
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

## 1. Confirm LLM access
```bash
python hello_llm.py        # prints a completion + token usage; fails loudly on bad key/quota
```

## 2. Build the vector store
Needs `backend/data/cars_clean.json` (Kangjie's cleaned NDJSON) — run
`python -m app.clean_data` in `backend/` first.
```bash
python build_index.py "fuel-efficient SUV"   # builds rag/faiss_index + demos a query
```
Embeddings are local (`sentence-transformers/all-MiniLM-L6-v2`) — no extra API key.
The Anthropic API has no embedding endpoint; for Timebox 3 we can compare this
against Voyage AI or Elasticsearch `dense_vector`.

## 3. Test queries
[test_queries.md](test_queries.md) — the natural-language queries the system must
handle, with expected structured-filter outputs, for evaluating the NL parser.

## How this feeds Timebox 3
- `hello_llm.py` → LLM client pattern reused by `backend/app/nl_search.py`
- `build_index.py` → embedding + retrieval layer for semantic recommendation
- `test_queries.md` → the eval set that scores parser + retrieval quality

Model: `claude-opus-4-8` (latest, most capable). Drop to `claude-haiku-4-5` if
NL-parse cost/latency becomes an issue at volume.
