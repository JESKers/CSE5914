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
/data       Kaggle data.csv + generated files (git-ignored) — except data/synth/,
            the committed synthetic finance/rental/dealer tables the assistant uses
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

Prereqs: Docker (Desktop or colima), Node 18+, a Kaggle account (dataset download),
Ollama with `llama3.2` and `nomic-embed-text`, and an Anthropic API key per person
for the AI Assistant (console.anthropic.com — the account needs API credit;
Claude app subscriptions don't cover API calls).

```bash
# 1. Env — fill in your own ANTHROPIC_API_KEY (required for /assistant + /recommend)
cp .env.example .env

# 2. Elasticsearch + Kibana + backend (build bakes the source into the image)
docker compose up -d --build

# 3. Seed the catalog: download data.csv from the Kaggle dataset linked above
#    into data/, then clean + ingest (data/ is volume-mounted into the container):
docker compose exec backend python -m search.clean_data   # data.csv -> cars_clean.json
docker compose exec backend python -m search.ingest       # cars_clean.json -> ES

# 4. (optional) snapshot vPIC model lists so /vpic/models answers offline:
docker compose exec backend python -m search.fetch_vpic_models
```

- Backend API docs: http://localhost:8000/docs · Health: http://localhost:8000/health
- Kibana: http://localhost:5601

Frontend (runs locally in dev):

```bash
cd frontend && npm install && npm run dev    # http://localhost:5173
```

Smoke test: http://localhost:8000/health should report `"elasticsearch": true`,
`/search?make=BMW` should return cars, and the **Assistant** page
(http://localhost:5173/assistant) should complete a rental end-to-end
(try: "Rent an SUV in Columbus this weekend, under $70/day").

### Gotchas

- **Backend code changes need an image rebuild** — the source is baked in:
  `docker compose up -d --build backend`. Changing only `.env` needs just
  `docker compose up -d backend` (recreate, no rebuild).
- **Empty search results** → step 3 wasn't run (the ES index is empty).
- **/assistant returns 503** → `ANTHROPIC_API_KEY` missing in `.env`;
  **400 "credit balance is too low"** → the key's account has no API credit.
- **ES container unhealthy / exits** → give Docker ≥ 4 GB memory.
- Runtime artifacts (`data/store.db` order ledger, `data/vehicle_images.json`
  photo cache) create themselves on first use — never commit them or `.env`.

The compose stack starts Ollama at http://localhost:11434. On a host-managed
Ollama installation, pull the required models with `ollama pull llama3.2` and
`ollama pull nomic-embed-text` before using `POST /api/recommend`.

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
- `GET /store/listings` · `POST /store/orders` — Buy/Rent store (additive; see docs/STORE_VPIC.md)
- `GET /vpic/decode/{vin}` · `GET /vpic/models` — NHTSA vPIC enrichment
- `POST /assistant/chat` — AI buy/rent agent: rentals booked end-to-end
  (inventory → add-ons → insurance → confirmation number), buy decisions with
  TCO/financing analysis, test-drive booking and dealer handoff
- `GET /assistant/bookings` — everything the agent has booked (demo surface)

Full details: [docs/API_CONTRACT.md](docs/API_CONTRACT.md).
