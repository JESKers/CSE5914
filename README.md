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

1. Copy the example env file and enable local Ollama settings.

```bash
cp .env.example .env
```

Then edit `.env` to include:

```dotenv
ES_HOST=http://elasticsearch:9200
ES_INDEX=cars
ES_USER=
ES_PASSWORD=

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=llama3.2
OLLAMA_EMBED_MODEL=nomic-embed-text

CORS_ORIGINS=http://localhost:5173,http://localhost:8080
```

> `ANTHROPIC_API_KEY` is optional. The current recommendation flow uses local Ollama `llama3.2`.

2. Start backend services and Ollama.

```bash
docker compose up -d
```

This launches:
- Elasticsearch: `http://localhost:9200`
- Kibana: `http://localhost:5601`
- Backend API: `http://localhost:8000`
- Ollama service: `http://localhost:11434`

3. Seed Elasticsearch with the car dataset.

```bash
docker compose exec backend python -m search.clean_data
docker compose exec backend python -m search.ingest
```

4. Start the frontend.

```bash
cd frontend
npm install
npm run dev
```

Open the app at `http://localhost:5173`.

### Verify it works

- Backend health: `http://localhost:8000/health`
- Backend docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`

### Alternative local backend run

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install -r search/requirements.txt
pip install -r rag/requirements.txt
uvicorn backend.app.main:app --reload
```

Run Ollama locally:

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
ollama serve
```

Then use the frontend or `POST /api/recommend` against `http://localhost:8000`.

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
