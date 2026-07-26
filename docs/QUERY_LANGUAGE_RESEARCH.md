# Vehicle-query language research

Research date: 2026-07-26

## What buyers actually write

This implementation was informed by public car-shopping filters and real buyer
requests. The sample is qualitative rather than a statistically representative
survey, but it exposes language that a simple `make + price` parser misses:

- Marketplace interfaces expose condition, price, year, mileage, make/model,
  body style, drivetrain, transmission, fuel, cylinders, doors, fuel economy,
  colors, safety, and installed features
  ([Cars.com](https://www.cars.com/shopping/advanced-search/),
  [Autotrader](https://www.autotrader.com/cars-for-sale/advanced-search),
  [Kelley Blue Book](https://www.kbb.com/car-finder/)).
- Buyers distinguish requirements from preferences: one request says AWD and
  four doors are mandatory while other features would merely be nice
  ([example](https://www.reddit.com/r/whatcarshouldIbuy/comments/16jggf1/)).
- Budgets are often flexible: "$35k, maybe $40k," "low $20s," or a preferred
  target plus an absolute ceiling
  ([example](https://www.reddit.com/r/whatcarshouldIbuy/comments/waa2yu/)).
- A single paragraph can mix family size, cargo, towing, MPG, body size, budget,
  condition, mileage, models already considered, and concerns about each
  ([family SUV example](https://www.reddit.com/r/whatcarshouldIbuy/comments/1phj2dy/best_3rd_row_suv_for_the_money/),
  [towing example](https://www.reddit.com/r/whatcarshouldIbuy/comments/r6i83m)).
- Context implies ranking goals: snow and a long commute imply all-weather and
  fuel-economy priorities
  ([commuter example](https://www.reddit.com/r/whatcarshouldIbuy/comments/1j79g7d/));
  an EV buyer may discuss daily distance, children, range, charging, and
  alternatives in the same request
  ([EV example](https://www.reddit.com/r/whatcarshouldIbuy/comments/1s9j6un/purchase_commute_ev/)).
- Buyers use exclusions and alternatives: "no SUV or truck," "Honda, Hyundai,
  or Kia," "sedan or hatchback," and named models they like or reject.
- Many requirements are listing-level or external facts, not attributes in this
  project's catalog: mileage, condition, seating capacity, towing, installed
  equipment, color, location, history, financing, ownership cost, safety
  ratings, EV range/charging, reliability, comfort, and off-road capability.

## Query semantics implemented

The parser separates four concepts instead of flattening every phrase into a
mandatory filter:

| Buyer language | Behavior |
| --- | --- |
| "must," "need," "at least," "under," "only" | Hard Elasticsearch filter |
| "prefer," "ideally," "would be nice," "around" | Elasticsearch score boost |
| "no," "not," "avoid," "anything but" | Elasticsearch `must_not` clause |
| Catalog cannot verify the requirement | Preserve it in `unsupported_preferences` and warn |

Supported hard constraints include:

- one or several makes/models, including common aliases;
- price, model year, horsepower, cylinders, and door-count ranges;
- city, highway, and combined MPG ranges;
- one or several body styles, vehicle sizes, drivetrains, transmissions,
  powertrains, and market categories;
- exclusions for makes, models, styles, drivetrains, transmissions,
  powertrains, and market categories.

Soft ranking supports target price/year/horsepower/MPG, preferred makes,
styles, sizes, drivetrains, powertrains, and market categories. It also derives
ranking goals such as affordability, fuel economy, city/highway use,
performance, all-weather use, family/cargo space, compactness, luxury, and
newer vehicles.

Examples now understood include:

```text
Ford or Mazda AWD coupe with at least 18 combined mpg,
no automatic, preferably under $45k, with CarPlay

Family SUV or wagon, ideally hybrid, 2020+, around $32.5k
but absolutely no more than $38k; avoid Tesla and rear-wheel drive

Cheap highway commuter, Honda/Hyundai/Kia, sedan or hatch,
30+ mpg preferred, manual would be nice, no diesel
```

The first two kinds of constraint change retrieval. `CarPlay` is retained in
the response warning because the committed catalog cannot prove that a
particular trim has it.

## Fuel-economy field

The source data has city and highway MPG but no combined value. The cleaning
pipeline stores combined MPG using the EPA gasoline-label weighting:

```text
combined_mpg = 1 / ((0.55 / city_mpg) + (0.45 / highway_mpg))
```

See the [EPA gasoline-label methodology](https://www.epa.gov/fueleconomy/text-version-gasoline-label).

## Evaluation discipline

`evaluation/queries.json` contains 348 labeled queries. It includes the original
regression cases plus researched real-world patterns and paraphrase matrices for
alternatives, negation, colloquial budgets, hard-versus-soft wording, and
dataset-boundary requirements.

Regenerate the corpus explicitly:

```bash
python evaluation/build_query_corpus.py
python evaluation/run_evaluation.py
```

An omitted expected field means the parser must leave it unset. Do not weaken a
label to match a parser bug; fix the parser or correct the label only when the
intended meaning was wrong.
