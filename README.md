# CSE5914 — JESKers Car Search

Smart car search & recommendation over the
[Kaggle car dataset](https://www.kaggle.com/datasets/CooperUnion/cardataset).

- **Timebox 2** — Elasticsearch-backed **Car Search System** (filter by brand, model,
  year, price, horsepower, engine, transmission + keywords). ← current
- **Timebox 3** — **Smart Recommendation** via RAG/LLM over free-text queries.

Plan: [docs/TIMEBOX2_PLAN.md](docs/TIMEBOX2_PLAN.md) · API: [docs/API_CONTRACT.md](docs/API_CONTRACT.md)

## Repo structure

```
/frontend   React + Vite UI (Shangrui)
/backend    FastAPI service — wires the API contract together (Eric)
/search     Elasticsearch index, ingestion, query core (Kangjie)
/rag        LLM hello-world, vector store, NL query parser (Jerry)
/data       Kaggle data.csv + generated cars_clean.json (git-ignored)
/docs       plan + API contract
```

The backend imports the `search` and `rag` packages, so Python commands run
from the **repo root** (`uvicorn backend.app.main:app`, `python -m search.ingest`).

| Area | Owner | Entry points |
|------|-------|--------------|
| Elasticsearch + query core | Kangjie | `search/{clean_data,ingest,search_service,index_mapping}.py` |
| RAG / NL parser | Jerry | `rag/{hello_llm,build_index,parser}.py`, `rag/test_queries.md` |
| Frontend | Shangrui | `frontend/` |
| Integration / API / ops | Eric | `backend/app/main.py`, `docker-compose.yml`, `docs/API_CONTRACT.md` |

## Quick start

```bash
cp .env.example .env                       # fill ANTHROPIC_API_KEY to test /recommend
docker compose up -d                       # Elasticsearch + Kibana + backend

# download data.csv from Kaggle into data/, then clean + seed ES (from repo root):
docker compose exec backend python -m search.clean_data   # data.csv -> cars_clean.json
docker compose exec backend python -m search.ingest       # cars_clean.json -> ES
```

- Backend API docs: http://localhost:8000/docs · Health: http://localhost:8000/health
- Kibana: http://localhost:5601

Frontend (runs locally in dev):

```bash
cd frontend && npm install && npm run dev    # http://localhost:5173
```

## Local dev — backend only

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload        # run from the repo root
pytest                                        # query-builder unit tests (no ES needed)
```

Owner-specific extras: `pip install -r search/requirements.txt` (Jupyter profiling),
`pip install -r rag/requirements.txt` (embeddings / FAISS).

## Branch strategy

- `main` — always runnable; protected. No direct pushes.
- Feature branches off `main`, one per task area:
  `search/<topic>`, `rag/<topic>`, `frontend/<topic>`, `backend/<topic>`
  (e.g. `search/index-mapping`, `frontend/results-grid`).
- Open a PR into `main`; at least one teammate reviews; squash-merge.
- Keep the API contract (`docs/API_CONTRACT.md` + `backend/app/schemas.py`) changes
  in their own PR so everyone sees the ripple.

## API summary

- `GET /search` — structured filters + `q` keyword search, sort, paging
- `GET /facets` — make / transmission / fuel-type buckets for dropdowns
- `POST /recommend` — free-text natural-language query (RAG, Timebox 3)

Full details: [docs/API_CONTRACT.md](docs/API_CONTRACT.md).
