# CSE5914 — JESKers Car Search

Smart car search & recommendation system. **Timebox 2** delivers an Elasticsearch-backed
**Car Search System** over the [Kaggle car dataset](https://www.kaggle.com/datasets/CooperUnion/cardataset).

See [docs/TIMEBOX2_PLAN.md](docs/TIMEBOX2_PLAN.md) for the full plan and role assignments.

## Architecture

```
frontend (static / nginx)  →  backend (FastAPI)  →  Elasticsearch
                                     └→ /nl-search → LLM parser (Timebox 3 spike)
```

| Area | Owner | Code |
|------|-------|------|
| Elasticsearch + query core | Kangjie | `backend/app/{ingest,search_service,index_mapping}.py` |
| NL→filter LLM spike | Jerry | `backend/app/nl_search.py` |
| Frontend | Shangrui | `frontend/` |
| Integration / API / ops | Eric | `backend/app/main.py`, `docker-compose.yml` |

## Quick start (Docker)

```bash
cp .env.example .env                       # fill ANTHROPIC_API_KEY if testing /nl-search
docker compose up -d                       # starts ES + backend + frontend

# one-time: download data.csv from Kaggle into backend/data/, then seed ES:
docker compose exec backend python -m app.ingest
```

- Frontend: http://localhost:8080
- API docs: http://localhost:8000/docs
- Health:   http://localhost:8000/health

## Local dev (backend only)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# point at a local ES; defaults to http://localhost:9200
uvicorn app.main:app --reload
pytest                                      # query-builder unit tests (no ES needed)
```

## API

- `GET /search` — structured filters + `q` keyword search, sorting, paging
- `GET /facets` — make / transmission / fuel-type buckets for dropdowns
- `POST /nl-search` — experimental natural-language search (Timebox 3 prep)
