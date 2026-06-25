# Buy / Rent Store + NHTSA vPIC (additive)

These endpoints are **additive** — they sit on top of the frozen
[API_CONTRACT.md](API_CONTRACT.md) (`/search`, `/facets`, `/models`,
`/recommend`) and do not change it. They turn the existing car catalog into a
storefront where customers can **filter, purchase, and rent** vehicles, and they
wire in the **[NHTSA vPIC API](https://vpic.nhtsa.dot.gov/api/)** for brand
verification and live vehicle data.

## Where the data comes from

vPIC is the authoritative source for vehicle make/model/spec data but publishes
**no prices and no inventory**. So:

| Concern | Source |
|---------|--------|
| make / model / specs / MSRP | Elasticsearch `cars` index (the existing catalog) |
| brand verification (`vpic_verified`) | vPIC make directory (`search/vpic.py`) |
| live models / VIN decode | vPIC live endpoints |
| `buy_price` | MSRP |
| `rent_daily`, `seats`, `for_rent`, `stock` | derived deterministically in `backend/app/store.py` |
| orders | SQLite ledger (`data/store.db`) |

Rental price ≈ `MSRP × 0.0008 + 18` per day (a ~$30k car rents around $40/day),
with a small premium for SUVs/pickups.

## Listing object

Extends the contract's Car object with store fields:

```json
{
  "id": "42", "make": "BMW", "model": "M4", "year": 2016, "msrp": 65000.0,
  "engine_hp": 425, "vehicle_style": "Coupe", "highway_mpg": 26, "city_mpg": 17,
  "buy_price": 65000.0,
  "rent_daily": 70.0,
  "seats": 4,
  "for_rent": true,
  "stock": 5,
  "vpic_verified": true
}
```

## `GET /store/listings`

Same filters as `/search` (`make`, `model`, `year_min/max`, `hp_min/max`,
`engine_fuel_type`, `transmission_type`, `q`, `sort`, `order`, `page`, `size`)
plus:

| Param | Notes |
|-------|-------|
| `mode` | `buy` (default) or `rent`. In `rent` mode only rentable units are returned and `price_min/max` are interpreted as **daily rent** (converted to an approximate MSRP range so ES still drives pagination). |
| `price_min`, `price_max` | buy price (MSRP) in buy mode; daily rent in rent mode |

Returns `{ results: [Listing], total, mode, page, size, query_echo }`.

```bash
# Buy: SUVs under $30k, best MPG first
curl "http://localhost:8000/store/listings?mode=buy&price_max=30000&sort=price&order=asc"

# Rent: BMWs up to $80/day
curl "http://localhost:8000/store/listings?mode=rent&make=BMW&price_max=80"
```

## `GET /store/vehicle/{id}`

One listing by catalog id (`404` if unknown).

## `POST /store/orders`

Purchase or rent. Body:

```json
{ "vehicle_id": "42", "mode": "rent", "rent_days": 5, "customer": "jane" }
```

- `buy` → total is `buy_price`; rejects with `409` if out of stock.
- `rent` → total is `rent_daily × rent_days`; rejects with `409` if not rentable.

Returns `{ order_id, vehicle, mode, rent_days, total, status, message }`.

## `GET /store/orders`

Order history (most recent first).

## `GET /vpic/decode/{vin}`

Live VIN decode via vPIC. `{ vin, summary, raw }` (`502` if vPIC is unreachable).

```bash
curl "http://localhost:8000/vpic/decode/1HGCM82633A004352"
```

## `GET /vpic/models?make=&year=`

Live model list for a make (optionally a model year) from vPIC.

---

**Run:** these endpoints need the `cars` index seeded (see the main README:
`python -m search.clean_data && python -m search.ingest`). vPIC calls require
outbound internet; if vPIC is down, `vpic_verified` falls back to `false` and
the `/vpic/*` endpoints return empty/`502`, but the store keeps working.
