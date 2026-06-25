# Natural-Language Test Queries

Owner: Jerry. The recommendation system must handle these plain-English queries.
Each lists the **expected structured filters** the NL parser (`backend/app/nl_search.py`)
should produce — use this as the evaluation set for Timebox 3.

Filter keys match `SearchFilters` in `backend/app/schemas.py`:
`make, model, year_min/max, price_min/max, hp_min/max, engine_fuel_type, transmission_type, q, sort, order`.

## Core examples (from the project spec)

| # | Query | Expected filters |
|---|-------|------------------|
| 1 | "fast sports car under $50,000" | `price_max=50000`, `hp_min≈300`, `q="sports coupe"`, `sort=hp`, `order=desc` |
| 2 | "fuel-efficient SUV" | `q="SUV"`, `sort=highway_mpg→` (high MPG), `engine_fuel_type` not diesel |
| 3 | "manual V8 coupe" | `transmission_type=MANUAL`, `q="coupe V8"`, `hp_min≈350` (V8 proxy) |

## Brand / model / year

| # | Query | Expected filters |
|---|-------|------------------|
| 4 | "newer Toyota under 30k" | `make=Toyota`, `year_min≈2015`, `price_max=30000` |
| 5 | "BMW 3 Series after 2014" | `make=BMW`, `model="3 Series"`, `year_min=2014` |
| 6 | "cheapest Honda available" | `make=Honda`, `sort=price`, `order=asc` |

## Performance / drivetrain

| # | Query | Expected filters |
|---|-------|------------------|
| 7 | "high horsepower muscle car" | `hp_min≈400`, `q="muscle coupe"`, `sort=hp`, `order=desc` |
| 8 | "automatic luxury sedan" | `transmission_type=AUTOMATIC`, `q="luxury sedan"` |
| 9 | "all-wheel drive under $40k" | `price_max=40000`, `q="all wheel drive"` |

## Economy / use-case / semantic

| # | Query | Expected filters |
|---|-------|------------------|
| 10 | "affordable family car with good gas mileage" | `price_max≈25000`, `q="sedan SUV"`, high MPG |
| 11 | "reliable commuter car" | `q="sedan compact"`, mid price, high MPG |
| 12 | "weekend convertible, money no object" | `q="convertible"`, `sort=hp`/`popularity`, no price cap |
| 13 | "electric or hybrid SUV" | `engine_fuel_type in {electric, hybrid}`, `q="SUV"` |
| 14 | "diesel truck for towing" | `engine_fuel_type=diesel`, `q="pickup truck"`, `hp_min` high |

## Edge cases (parser robustness)

| # | Query | Expected behavior |
|---|-------|-------------------|
| 15 | "something fun" | very loose: `q="sports convertible"`, no hard filters |
| 16 | "car under 5 dollars" | `price_max=5` → returns 0 results gracefully |
| 17 | "fast" (one word) | `sort=hp`, `order=desc`, no other filters |

## Evaluation notes
- **Pass = parsed filters are reasonable** (price/year/transmission numerically correct;
  fuzzy descriptors land in `q`). Semantic terms ("fast", "luxury", "fuel-efficient")
  have no exact column, so they map to a mix of `q` + range filters.
- Run each query through `parse_query()` and diff against this table.
- Track: filter precision, result relevance (top-5 manually judged), latency, cost.
