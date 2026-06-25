# JESKers — Smart Car Recommendation, Purchase & Rental System

A car storefront where customers **filter, get recommendations, purchase, or
rent** vehicles by brand, price, body style, fuel, and more.

The catalog is backed by the **[NHTSA vPIC API](https://vpic.nhtsa.dot.gov/api/)**
for authoritative make/model/spec data, joined with **MSRP pricing from
`data/data.csv`** (vPIC does not publish prices or rental inventory). Each daily
rental rate is derived from MSRP.

## Architecture

```
┌────────────┐   filter / recommend / buy / rent   ┌──────────────────┐
│  Frontend  │ ───────────────────────────────────▶│  FastAPI backend │
│ static/*   │                                      │  app/main.py     │
└────────────┘                                      └────────┬─────────┘
                                                             │
                          ┌──────────────────────────────────┼───────────────────────┐
                          ▼                                  ▼                          ▼
                 ┌─────────────────┐              ┌────────────────────┐     ┌──────────────────┐
                 │ SQLite catalog  │              │  NHTSA vPIC API     │     │  Recommender     │
                 │ app/db.py       │◀── seeded ──▶│  app/vpic.py        │     │  app/recommend.py│
                 │ (data.csv MSRP) │   verified   │  brands / models /  │     │  scoring + reasons│
                 └─────────────────┘   makes      │  specs / VIN decode │     └──────────────────┘
                                                  └────────────────────┘
```

- **`app/vpic.py`** — cached client for the vPIC API (make directory, models per
  make/year, vehicle types, VIN decode). Degrades gracefully if vPIC is offline.
- **`app/db.py`** — SQLite schema + seeder. Builds the catalog from `data.csv`,
  verifies every brand against the vPIC make directory (`vpic_make_id`), and
  derives `buy_price`, `rent_daily`, `seats`, rental availability, and stock.
- **`app/recommend.py`** — scores candidates 0–100 with human-readable reasons.
- **`app/main.py`** — FastAPI: filtering, recommendation, buy/rent orders, live
  vPIC endpoints; serves the frontend from `static/`.

## Run it

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload          # or: python main.py
```

Then open **http://localhost:8000** for the storefront, or
**http://localhost:8000/docs** for the API.

The first request seeds `data/cars.db` from `data/data.csv` and the vPIC make
directory (a few seconds). To rebuild the catalog from scratch:

```bash
python -m app.db          # re-seeds data/cars.db
```

With Docker: `docker-compose up --build` (single service, no Elasticsearch).

## Key API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/api/health` | catalog status |
| GET  | `/api/filters` | facet values + price/year ranges for the UI |
| GET  | `/api/makes` | brand directory with vPIC verification flags |
| GET  | `/api/vehicles` | **filter** by `make`, `min_price`/`max_price`, `body_style`, `fuel_type`, `drive`, `year_min`, `min_seats`, `q`, `mode=buy\|rent`, `sort`, `page` |
| GET  | `/api/vehicles/{id}` | vehicle detail |
| GET  | `/api/vehicles/{id}/vpic` | **live** vPIC enrichment (vehicle types + models) |
| GET  | `/api/vpic/models?make=&year=` | live vPIC model lookup |
| GET  | `/api/vpic/decode/{vin}` | live VIN decode via vPIC |
| POST | `/api/recommend` | ranked recommendations with match scores + reasons |
| POST | `/api/orders` | **purchase or rent** a vehicle |
| GET  | `/api/orders` | order history |

### Example: filter cheap fuel-efficient SUVs to buy

```bash
curl "http://localhost:8000/api/vehicles?body_style=4dr%20SUV&max_price=30000&sort=mpg"
```

### Example: rent a vehicle

```bash
curl -X POST http://localhost:8000/api/orders \
  -H 'Content-Type: application/json' \
  -d '{"vehicle_id": 1, "mode": "rent", "rent_days": 5}'
```
