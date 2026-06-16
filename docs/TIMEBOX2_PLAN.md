# Timebox 2 Plan — Car Search System (JESKers)

**Goal:** A working **Car Search System**. Users search the Kaggle car dataset by
**brand, model, year, price, horsepower, engine type, transmission, and free-text
keywords**, powered by **Elasticsearch** behind a web app.

**Dataset:** [Kaggle CooperUnion/cardataset](https://www.kaggle.com/datasets/CooperUnion/cardataset) — `data.csv`, ~11,914 rows.
Columns: `Make, Model, Year, Engine Fuel Type, Engine HP, Engine Cylinders,
Transmission Type, Driven_Wheels, Number of Doors, Market Category, Vehicle Size,
Vehicle Style, highway MPG, city mpg, Popularity, MSRP`.

> Note: Elasticsearch is the Timebox 2 deliverable. RAG/LLM is the Timebox 3 deliverable —
> Jerry's work below is a **de-risking spike** that prepares for Timebox 3, not a blocker for the Timebox 2 demo.

---

## Architecture

```
[ Web app (Shangrui) ]
        │  HTTP/JSON
        ▼
[ FastAPI backend (Eric) ] ──► [ Elasticsearch (Kangjie) ]
        │
        └─ /nl-search (experimental) ──► [ LLM query parser (Jerry) ]
```

- **Backend:** Python + FastAPI (team already uses Python + OpenAI/Anthropic SDKs).
- **Search:** Elasticsearch 8.x in Docker, single `cars` index.
- **Frontend:** Web app (React or lightweight) calling the backend's JSON API.
- **Orchestration:** `docker-compose` (Elasticsearch + backend + frontend).

---

## Roles & Tasks

### 🔍 Kangjie — Elasticsearch (owner of the search core)
1. Stand up Elasticsearch (+ Kibana for debugging) via Docker.
2. Define the `cars` index mapping:
   - keyword fields: `make`, `model`, `transmission_type`, `engine_fuel_type`, `vehicle_style`, `driven_wheels`
   - numeric fields: `year`, `engine_hp`, `engine_cylinders`, `msrp`, `highway_mpg`, `city_mpg`, `popularity`
   - a combined `text` field (`make + model + market_category + vehicle_style`) with an
     analyzer for keyword/full-text search.
3. Write the ingestion script (`ingest.py`): parse `data.csv`, clean nulls (e.g. `N/A` HP),
   bulk-index into `cars`.
4. Build the query layer (`search_service.py`):
   - structured filters (term/range) for brand, model, year, price, HP, engine, transmission
   - full-text `multi_match` for the keyword box
   - sorting (price, year, HP, popularity) + pagination
5. **Deliverable:** a `search(filters, keyword, sort, page)` function returning normalized results + facet counts.

### 🤖 Jerry — RAG/LLM spike (prep for Timebox 3)
1. Set up the LLM client (reuse `anthropic` client pattern from `phase 2/project1`; default to a current Claude model).
2. Build a **natural-language → structured-filter parser**: given `"fast sports car under $50,000"`,
   the LLM returns JSON `{vehicle_style, msrp_max, engine_hp_min, ...}` matching Kangjie's filter schema.
3. Validate the JSON against the filter schema, then hand it to Kangjie's `search()`.
4. Prototype the `/nl-search` endpoint (can be behind a feature flag / "experimental" tab).
5. Document findings for Timebox 3 (semantic embeddings vs. structured parsing, model choice, cost).
6. **Deliverable:** working NL→filter translation on 5–10 sample queries + a short design note.

### 🎨 Shangrui — Frontend (web app)
1. Scaffold the web app and a search page.
2. Search form: dropdowns (brand→model dependent, year, transmission, engine type),
   numeric inputs/sliders (price range, HP range), keyword text box.
3. Results: car cards (make/model/year, price, HP, engine, transmission), sorting controls, pagination.
4. Empty/loading/error states; wire to the backend's JSON contract.
5. (Stretch) an "experimental" search box that hits Jerry's `/nl-search`.
6. **Deliverable:** functional UI that returns and displays live search results.

### 🔗 Eric — Integration (glue + ops)
1. Repo scaffolding: `backend/`, `frontend/`, `docker-compose.yml`, `.env.example`, root `README` run instructions.
2. FastAPI app: define the JSON API contract and wire endpoints to Kangjie's `search_service`:
   - `GET /search` (structured + keyword), `GET /facets`, `POST /nl-search` (Jerry).
3. CORS, env/config management, ES connection handling, basic error handling.
4. `docker-compose up` brings up ES + backend + frontend end-to-end.
5. Smoke tests + a seed/ingest make target; light CI (lint + a couple of API tests).
6. **Deliverable:** one-command local run, green end-to-end smoke test.

---

## API Contract (agree on this Day 1 — Eric owns)

```
GET /search?
    make=&model=&year_min=&year_max=&price_min=&price_max=
    &hp_min=&hp_max=&engine_fuel_type=&transmission_type=
    &q=<keywords>&sort=<price|year|hp|popularity>&order=<asc|desc>&page=&size=
→ { total, page, size, results: [ {id, make, model, year, msrp, engine_hp,
    engine_fuel_type, transmission_type, vehicle_style, ...} ] }

GET /facets → { makes:[{key,count}], transmissions:[...], fuel_types:[...] }

POST /nl-search  body: { "query": "fast sports car under $50,000" }
→ { parsed_filters: {...}, results: [...] }   # experimental
```

---

## Milestones (within the timebox)

| Phase | What | Who | Blocks |
|-------|------|-----|--------|
| M1 — Foundations | Repo scaffold, docker-compose, ES up, **API contract frozen** | Eric + Kangjie | everything |
| M2 — Core search | Index mapping + ingestion + structured/keyword query | Kangjie | M1 |
| M3 — UI + wiring | Frontend form/results ↔ `/search`, `/facets` live | Shangrui + Eric | M2 |
| M4 — NL spike | `/nl-search` parser prototype on sample queries | Jerry | M2 |
| M5 — Demo polish | End-to-end smoke test, README, demo script | All | M3 |

## Definition of Done (Timebox 2 demo)
- `docker-compose up` → working search UI against the full Kaggle dataset.
- Filter by brand/model/year/price/HP/engine/transmission **and** free-text keywords; results sorted + paginated.
- (Stretch) NL query box translating plain English into a filtered search.

## Risks / Decisions to make early
- **Frontend stack** (React vs. plain HTML/JS) — Shangrui to pick.
- **Dependent dropdowns** (model list depends on selected make) — needs a `/facets` or `/models?make=` endpoint.
- **Data cleaning** — `Engine HP`/`Engine Cylinders` have nulls; decide drop vs. default.
- **ES in CI** — keep heavy ES tests local; CI does lint + mocked API tests.
