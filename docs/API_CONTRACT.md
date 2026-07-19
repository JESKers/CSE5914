# API Contract (v0.1)

Owner: Eric (Integration). **Frozen for Timebox 2** — changes here ripple to
the frontend (Shangrui), search core (Kangjie), and RAG parser (Jerry), so
discuss before editing. Source of truth: [backend/app/schemas.py](../backend/app/schemas.py).

Base URL (local): `http://localhost:8000`

## Response envelope

Every search-style response uses one envelope:

```json
{
  "results": [ /* Car objects */ ],
  "total": 1234,
  "query_echo": { /* the filters or query that produced these results */ }
}
```

`/search` also includes `page` and `size`.

### Car object

```json
{
  "id": "42",
  "make": "BMW",
  "model": "M4",
  "year": 2016,
  "msrp": 65000.0,
  "engine_hp": 425,
  "engine_fuel_type": "premium unleaded (required)",
  "transmission_type": "MANUAL",
  "vehicle_style": "Coupe",
  "highway_mpg": 26,
  "city_mpg": 17
}
```

---

## `GET /health`

Liveness + ES connectivity.

```json
{ "status": "ok", "elasticsearch": true }
```

## `GET /search` — structured filters + keyword

Query params (all optional):

| Param | Type | Notes |
|-------|------|-------|
| `make`, `model` | string | exact term match |
| `year_min`, `year_max` | int | inclusive range |
| `price_min`, `price_max` | number | MSRP range |
| `hp_min`, `hp_max` | int | horsepower range |
| `engine_fuel_type` | string | exact term |
| `transmission_type` | string | `MANUAL` / `AUTOMATIC` / `AUTOMATED_MANUAL` / ... |
| `q` | string | free-text keyword search (fuzzy) |
| `sort` | string | `price` \| `year` \| `hp` \| `popularity` (default `popularity`) |
| `order` | string | `asc` \| `desc` (default `desc`) |
| `page` | int ≥1 | default 1 |
| `size` | int 1–100 | default 20 |

Example: `GET /search?make=BMW&price_max=50000&q=coupe&sort=hp&order=desc`

Returns the envelope (with `page`, `size`); `query_echo` is the applied filters.

## `GET /facets` — dropdown values

Aggregation buckets for the filter UI.

```json
{
  "makes":         [ { "key": "Chevrolet", "count": 1123 }, ... ],
  "transmissions": [ { "key": "AUTOMATIC", "count": 8266 }, ... ],
  "fuel_types":    [ { "key": "regular unleaded", "count": 7172 }, ... ],
  "years":         [ 2017, 2016, 2015, ... ]
}
```

`years` is the distinct list of years in the data (newest first) — it populates
the year-range dropdowns in the filter UI.

## `GET /models?make=` — models for a make (dependent dropdown)

Distinct model names for one make, alphabetically sorted. Drives the Model
dropdown, which is enabled once a make is chosen. `make` is required (`422` if
missing).

```
GET /models?make=BMW
→ { "make": "BMW", "models": ["1 Series", "2 Series", "3 Series", ...] }
```

## `POST /recommend` — free-text natural language (RAG)

Body:

```json
{ "query": "fast sports car under $50,000" }
```

The deterministic parser turns the query into structured filters, then runs the
same Elasticsearch search. Hard constraints are verified again before a car is
returned. `query_echo` carries the original query and parsed filters, while each
result includes evidence-based `match_reasons`:

```json
{
  "results": [
    {
      "id": "42",
      "make": "Ford",
      "model": "Mustang",
      "year": 2018,
      "msrp": 42000,
      "engine_hp": 460,
      "match_reasons": [
        "MSRP $42,000 is within the $50,000 limit",
        "460 hp meets the 300 hp minimum"
      ]
    }
  ],
  "total": 5,
  "message": "Found 5 vehicles that satisfy the extracted hard constraints.",
  "query_echo": {
    "query": "fast sports car under $50,000",
    "parsed_filters": { "price_max": 50000, "hp_min": 300, "q": "sports coupe", "sort": "hp", "order": "desc" }
  }
}
```

The endpoint does not require an LLM to enforce constraints. Generated narrative
can be layered on later, but stored Elasticsearch facts remain authoritative.

---

## Example requests (curl)

Assumes the backend is up (`uvicorn backend.app.main:app` or `docker compose up`)
and the `cars` index is seeded.

```bash
# Health + ES connectivity
curl -s http://localhost:8000/health

# Keyword search (synonym-aware: "chevy" also matches Chevrolet)
curl -s "http://localhost:8000/search?q=chevy&size=5"

# Structured filters: BMWs under $50k, sorted by horsepower
curl -s "http://localhost:8000/search?make=BMW&price_max=50000&sort=hp&order=desc"

# Combined filters + keyword + paging
curl -s "http://localhost:8000/search?year_min=2014&year_max=2017&hp_min=300&q=coupe&page=2&size=10"

# Dropdown values for the filter UI
curl -s http://localhost:8000/facets

# Validation: inverted range -> 400
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8000/search?price_min=50000&price_max=10000"

# No matches -> 200 with an empty results array
curl -s "http://localhost:8000/search?make=Nonesuch"
```
