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
  "fuel_types":    [ { "key": "regular unleaded", "count": 7172 }, ... ]
}
```

## `POST /recommend` — free-text natural language (RAG)

Body:

```json
{ "query": "fast sports car under $50,000" }
```

The LLM parser (Jerry) turns the query into structured filters, then runs the
same search. Returns the envelope; `query_echo` carries the original query and
the parsed filters:

```json
{
  "results": [ /* Car objects */ ],
  "total": 37,
  "query_echo": {
    "query": "fast sports car under $50,000",
    "parsed_filters": { "price_max": 50000, "hp_min": 300, "q": "sports coupe", "sort": "hp", "order": "desc" }
  }
}
```

Returns `503` if `ANTHROPIC_API_KEY` is not configured. Experimental in Timebox 2;
the primary recommendation deliverable in Timebox 3.
