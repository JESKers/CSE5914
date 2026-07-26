"""Build the committed real-world natural-language query benchmark.

The base cases predate the extended query schema. This script applies explicit
label additions for those cases and appends paraphrased patterns observed in
car-shopping forums and major inventory search tools. The generated JSON remains
the reviewable source used by CI; this script makes the larger corpus repeatable.
"""
from __future__ import annotations

import json
from pathlib import Path


QUERY_FILE = Path(__file__).with_name("queries.json")
STYLE = {
    "suv": ["4dr SUV", "2dr SUV", "Convertible SUV"],
    "truck": ["Crew Cab Pickup", "Extended Cab Pickup", "Regular Cab Pickup"],
    "hatch": ["4dr Hatchback", "2dr Hatchback"],
    "minivan": ["Passenger Minivan", "Cargo Minivan"],
}

UPDATE_EXISTING = {
    "price-010": {"preferred_price_max": 30000},
    "price-011": {"ranking_preferences": ["affordability"]},
    "price-012": {"ranking_preferences": ["affordability", "fuel_economy"]},
    "price-013": {
        "vehicle_styles": STYLE["suv"],
        "ranking_preferences": ["affordability"],
    },
    "year-012": {"ranking_preferences": ["newer"]},
    "hp-009": {"ranking_preferences": ["performance"]},
    "make-002": {"vehicle_styles": ["Sedan"]},
    "make-003": {"vehicle_styles": STYLE["truck"]},
    "make-004": {"vehicle_styles": STYLE["suv"]},
    "make-005": {"vehicle_styles": ["Coupe"]},
    "make-006": {"vehicle_styles": STYLE["hatch"]},
    "make-008": {"vehicle_styles": ["Wagon"]},
    "make-009": {"vehicle_styles": ["Sedan"]},
    "make-010": {"makes": ["honda", "toyota"]},
    "make-011": {"excluded_makes": ["ford"]},
    "make-012": {"market_categories": ["Performance"]},
    "make-013": {"vehicle_styles": STYLE["suv"]},
    "make-015": {"ranking_preferences": ["fuel_economy"]},
    "powertrain-003": {"vehicle_styles": ["Coupe"]},
    "powertrain-004": {"excluded_transmission_types": ["AUTOMATIC"]},
    "powertrain-007": {"ranking_preferences": ["fuel_economy"]},
    "powertrain-008": {"vehicle_styles": STYLE["truck"]},
    "powertrain-009": {
        "market_categories": ["Hybrid"],
        "vehicle_styles": ["Sedan"],
    },
    "powertrain-010": {
        "market_categories": ["Hybrid"],
        "unsupported_preferences": ["plug-in capability"],
    },
    "powertrain-011": {"powertrains": ["gasoline"]},
    "powertrain-012": {"excluded_powertrains": ["diesel"]},
    "combined-002": {"vehicle_styles": ["Coupe"]},
    "combined-006": {"ranking_preferences": ["affordability"]},
    "combined-009": {"vehicle_styles": ["Wagon"]},
    "combined-013": {"market_categories": ["Luxury"]},
    "combined-014": {"ranking_preferences": ["fuel_economy"]},
    "combined-017": {"ranking_preferences": ["affordability"]},
    "soft-001": {
        "vehicle_styles": STYLE["suv"],
        "ranking_preferences": ["family_space"],
        "unsupported_preferences": ["reliability history"],
    },
    "soft-002": {
        "ranking_preferences": ["highway_driving"],
        "unsupported_preferences": ["ride comfort"],
    },
    "soft-003": {"ranking_preferences": ["affordability"]},
    "soft-004": {"ranking_preferences": ["performance"]},
    "soft-005": {"unsupported_preferences": ["safety ratings"]},
    "soft-006": {
        "ranking_preferences": ["highway_driving", "family_space", "cargo_space"],
    },
    "soft-007": {
        "ranking_preferences": ["fuel_economy"],
        "unsupported_preferences": ["ownership costs"],
    },
    "soft-008": {"ranking_preferences": ["performance"]},
    "soft-009": {
        "ranking_preferences": ["luxury"],
        "unsupported_preferences": ["ride comfort"],
    },
    "soft-010": {"ranking_preferences": ["fuel_economy"]},
    "robust-005": {"vehicle_styles": STYLE["truck"]},
    "adversarial-006": {"excluded_powertrains": ["electric"]},
}

REMOVE_EXISTING_FIELDS = {
    case_id: ["price_max"]
    for case_id in (
        "price-011",
        "price-012",
        "price-013",
        "combined-006",
        "combined-017",
        "soft-003",
    )
}


def build_new_cases() -> list[dict]:
    cases: list[dict] = []

    def add(case_id, query, expected, *tags):
        cases.append({
            "id": f"rw-{case_id}",
            "query": query,
            "expected_filters": expected,
            "tags": ["real-world", *tags],
        })

    # Budget language: caps, bands, targets, flexible ceilings, and minimums.
    price_max_cases = [
        ("price-max-01", "I can spend up to $32,000", 32000),
        ("price-max-02", "keep it below 18 grand", 18000),
        ("price-max-03", "my max budget is 42k", 42000),
        ("price-max-04", "price limit of $27,500", 27500),
        ("price-max-05", "budget of $15,000", 15000),
        ("price-max-06", "I have 22k to spend", 22000),
        ("price-max-07", "the price must not exceed $60k", 60000),
        ("price-max-08", "$45k max", 45000),
        ("price-max-09", "no more than 33 thousand dollars", 33000),
        ("price-max-10", "at most $19,999", 19999),
        ("price-max-11", "anything costing $55,000 or less", 55000),
        ("price-max-12", "car <= 24k", 24000),
    ]
    for case_id, query, value in price_max_cases:
        add(case_id, query, {"price_max": value}, "price", "paraphrase")

    price_ranges = [
        ("price-range-01", "between $20k and $30k", 20000, 30000),
        ("price-range-02", "from 12000 to 18000 dollars", 12000, 18000),
        ("price-range-03", "$25k-$35k budget", 25000, 35000),
        ("price-range-04", "price range of 40 thousand to 55 thousand", 40000, 55000),
        ("price-range-05", "looking in the $8,000-$12,000 range", 8000, 12000),
        ("price-range-06", "cars from 65k to 80k", 65000, 80000),
    ]
    for case_id, query, low, high in price_ranges:
        add(case_id, query, {"price_min": low, "price_max": high}, "price", "range")

    preferred_prices = [
        ("price-soft-01", "around $30k", 30000),
        ("price-soft-02", "roughly 22 grand", 22000),
        ("price-soft-03", "about $47,500", 47500),
        ("price-soft-04", "target budget is 35k", 35000),
    ]
    for case_id, query, value in preferred_prices:
        add(case_id, query, {"preferred_price_max": value}, "price", "soft-constraint")

    stretch_prices = [
        ("price-stretch-01", "budget is 35k but I can stretch to 40k", 35000, 40000),
        ("price-stretch-02", "preferably under 30k, absolute max 36k", 30000, 36000),
        ("price-stretch-03", "stay under 25k but can go up to 28k", 25000, 28000),
    ]
    for case_id, query, preferred, maximum in stretch_prices:
        add(case_id, query, {
            "preferred_price_max": preferred, "price_max": maximum,
        }, "price", "trade-off")
    add(
        "price-dual-cue-01",
        "around $32.5k but absolutely no more than $38k",
        {"preferred_price_max": 32500, "price_max": 38000},
        "price",
        "hard-vs-soft",
    )

    for case_id, query, low, high in [
        ("price-band-01", "something in the low 20s", 20000, 25000),
        ("price-band-02", "a car in the mid-30s", 33000, 37000),
        ("price-band-03", "budget is in the high 40s", 47000, 50000),
    ]:
        add(case_id, query, {"price_min": low, "price_max": high}, "price", "colloquial")

    for case_id, query, minimum in [
        ("price-min-01", "at least $12,000", 12000),
        ("price-min-02", "more than $25k", 25001),
        ("price-min-03", "over 40 grand", 40001),
    ]:
        add(case_id, query, {"price_min": minimum}, "price", "lower-bound")

    # Model-year language, including relative ranges grounded in the catalog.
    year_cases = [
        ("year-01", "2014 through 2017", {"year_min": 2014, "year_max": 2017}),
        ("year-02", "from 2012 to 2016", {"year_min": 2012, "year_max": 2016}),
        ("year-03", "2010-2013 models", {"year_min": 2010, "year_max": 2013}),
        ("year-04", "2015 or newer", {"year_min": 2015}),
        ("year-05", "no older than 2013", {"year_min": 2013}),
        ("year-06", "newer than 2011", {"year_min": 2012}),
        ("year-07", "made after 2010", {"year_min": 2011}),
        ("year-08", "before 2016", {"year_max": 2015}),
        ("year-09", "2012 or older", {"year_max": 2012}),
        ("year-10", "older than 2014", {"year_max": 2013}),
        ("year-11", "a 2009 model", {"year_min": 2009, "year_max": 2009}),
        ("year-12", "from 2016", {"year_min": 2016, "year_max": 2016}),
        ("year-13", "last 3 model years", {"year_min": 2015, "year_max": 2017}),
        ("year-14", "past 5 years", {"year_min": 2013, "year_max": 2017}),
        ("year-15", "prefer 2014 or newer", {"preferred_year_min": 2014}),
    ]
    for case_id, query, expected in year_cases:
        add(case_id, query, expected, "year", "paraphrase")
    add("year-plus-01", "2020+ only", {"year_min": 2020}, "year", "symbolic")
    add(
        "year-plus-soft-01",
        "2018+ preferred",
        {"preferred_year_min": 2018},
        "year",
        "symbolic",
        "hard-vs-soft",
    )

    # Horsepower, cylinders, doors, and fuel economy from catalog fields.
    numeric_cases = [
        ("hp-01", "at least 275 horsepower", {"hp_min": 275}, "horsepower"),
        ("hp-02", "400+ hp", {"hp_min": 400}, "horsepower"),
        ("hp-03", "more than 350 hp", {"hp_min": 351}, "horsepower"),
        ("hp-04", "under 250 horsepower", {"hp_max": 249}, "horsepower"),
        ("hp-05", "between 200 and 320 hp", {"hp_min": 200, "hp_max": 320}, "horsepower"),
        ("hp-06", "exactly 300 hp", {"hp_min": 300, "hp_max": 300}, "horsepower"),
        ("hp-07", "prefer at least 450 hp", {"preferred_hp_min": 450}, "horsepower"),
        ("cyl-01", "a V8 car", {"engine_cylinders_min": 8, "engine_cylinders_max": 8}, "cylinders"),
        ("cyl-02", "six cylinder SUV", {
            "engine_cylinders_min": 6, "engine_cylinders_max": 6,
            "vehicle_styles": STYLE["suv"],
        }, "cylinders"),
        ("cyl-03", "at least 6 cylinders", {"engine_cylinders_min": 6}, "cylinders"),
        ("cyl-04", "no more than 4 cylinders", {"engine_cylinders_max": 4}, "cylinders"),
        ("cyl-05", "between 4 and 8 cylinders", {
            "engine_cylinders_min": 4, "engine_cylinders_max": 8,
        }, "cylinders"),
        ("door-01", "a 2-door car", {
            "number_of_doors_min": 2, "number_of_doors_max": 2,
        }, "doors"),
        ("door-02", "four door sedan", {
            "number_of_doors_min": 4, "number_of_doors_max": 4,
            "vehicle_styles": ["Sedan"],
        }, "doors"),
        ("door-03", "at least 4 doors", {"number_of_doors_min": 4}, "doors"),
        ("mpg-01", "at least 30 mpg", {"combined_mpg_min": 30}, "mpg"),
        ("mpg-02", "35+ combined mpg", {"combined_mpg_min": 35}, "mpg"),
        ("mpg-03", "minimum 28 highway mpg", {
            "highway_mpg_min": 28,
            "ranking_preferences": ["highway_driving"],
        }, "mpg"),
        ("mpg-04", "at least 25 city mpg", {"city_mpg_min": 25}, "mpg"),
        ("mpg-05", "between 20 and 30 mpg", {
            "combined_mpg_min": 20, "combined_mpg_max": 30,
        }, "mpg"),
        ("mpg-06", "under 22 mpg", {"combined_mpg_max": 21}, "mpg"),
        ("mpg-07", "prefer 32+ mpg", {"preferred_combined_mpg_min": 32}, "mpg"),
    ]
    for case_id, query, expected, tag in numeric_cases:
        add(case_id, query, expected, tag, "structured")

    # Makes, alternatives, exclusions, body style, and size.
    categorical_cases = [
        ("make-01", "Honda or Toyota", {"makes": ["honda", "toyota"]}, "make"),
        ("make-02", "BMW, Audi, or Mercedes", {
            "makes": ["bmw", "audi", "mercedes-benz"],
        }, "make"),
        ("make-03", "anything but Nissan", {"excluded_makes": ["nissan"]}, "negation"),
        ("make-04", "avoid Ford and Chevy", {
            "excluded_makes": ["ford", "chevrolet"],
        }, "negation"),
        ("make-05", "prefer Mazda but open to Honda", {
            "preferred_makes": ["mazda", "honda"],
        }, "soft-constraint"),
        ("style-01", "SUV or wagon", {
            "vehicle_styles": STYLE["suv"] + ["Wagon"],
        }, "body-style"),
        ("style-02", "no sedans", {"excluded_vehicle_styles": ["Sedan"]}, "negation"),
        ("style-03", "avoid trucks and minivans", {
            "excluded_vehicle_styles": STYLE["truck"] + STYLE["minivan"],
        }, "negation"),
        ("style-04", "prefer a hatchback", {
            "preferred_vehicle_styles": STYLE["hatch"],
        }, "soft-constraint"),
        ("style-05", "convertible or coupe", {
            "vehicle_styles": ["Convertible", "Coupe"],
        }, "body-style"),
        ("style-06", "a van for passengers", {
            "vehicle_styles": ["Passenger Van", "Cargo Van"],
        }, "body-style"),
        ("size-01", "compact car", {
            "vehicle_sizes": ["Compact"],
            "ranking_preferences": ["compact"],
        }, "vehicle-size"),
        ("size-02", "midsize or large SUV", {
            "vehicle_styles": STYLE["suv"],
            "vehicle_sizes": ["Midsize", "Large"],
        }, "vehicle-size"),
        ("size-03", "prefer a small hatchback", {
            "preferred_vehicle_styles": STYLE["hatch"],
            "preferred_vehicle_sizes": ["Compact"],
            "ranking_preferences": ["compact"],
        }, "vehicle-size"),
        ("market-01", "luxury sedan", {
            "vehicle_styles": ["Sedan"], "market_categories": ["Luxury"],
        }, "market-category"),
        ("market-02", "performance coupe", {
            "vehicle_styles": ["Coupe"], "market_categories": ["Performance"],
        }, "market-category"),
        ("market-03", "prefer luxury but not exotic", {
            "preferred_market_categories": ["Luxury"],
            "excluded_market_categories": ["Exotic"],
        }, "market-category"),
    ]
    for case_id, query, expected, tag in categorical_cases:
        add(case_id, query, expected, tag)

    # Drivetrain, transmission, and powertrain alternatives and exclusions.
    mechanical_cases = [
        ("drive-01", "must have AWD", {"driven_wheels": ["all wheel drive"]}, "drivetrain"),
        ("drive-02", "AWD or 4WD", {
            "driven_wheels": ["all wheel drive", "four wheel drive"],
        }, "drivetrain"),
        ("drive-03", "prefer rear wheel drive", {
            "preferred_driven_wheels": ["rear wheel drive"],
        }, "drivetrain"),
        ("drive-04", "no front wheel drive", {
            "excluded_driven_wheels": ["front wheel drive"],
        }, "drivetrain"),
        ("drive-05", "4x4 truck", {
            "driven_wheels": ["four wheel drive"],
            "vehicle_styles": STYLE["truck"],
        }, "drivetrain"),
        ("trans-01", "manual only", {"transmission_type": "MANUAL"}, "transmission"),
        ("trans-02", "avoid automatics", {
            "excluded_transmission_types": ["AUTOMATIC"],
        }, "transmission"),
        ("trans-03", "manual or DCT", {
            "transmission_types": ["AUTOMATED_MANUAL", "MANUAL"],
        }, "transmission"),
        ("trans-04", "direct drive EV", {
            "transmission_type": "DIRECT_DRIVE",
            "engine_fuel_type": "electric",
        }, "transmission"),
        ("fuel-01", "hybrid or electric", {
            "powertrains": ["electric", "hybrid"],
        }, "powertrain"),
        ("fuel-02", "diesel only", {"engine_fuel_type": "diesel"}, "powertrain"),
        ("fuel-03", "gasoline car", {"powertrains": ["gasoline"]}, "powertrain"),
        ("fuel-04", "prefer a hybrid", {
            "preferred_powertrains": ["hybrid"],
        }, "powertrain"),
        ("fuel-05", "no diesel or electric cars", {
            "excluded_powertrains": ["electric", "diesel"],
        }, "negation"),
        ("fuel-06", "flex-fuel truck", {
            "powertrains": ["flex-fuel"], "vehicle_styles": STYLE["truck"],
        }, "powertrain"),
        ("fuel-07", "plug-in hybrid SUV", {
            "market_categories": ["Hybrid"],
            "vehicle_styles": STYLE["suv"],
            "unsupported_preferences": ["plug-in capability"],
        }, "powertrain"),
    ]
    for case_id, query, expected, tag in mechanical_cases:
        add(case_id, query, expected, tag)

    # Unsupported requirements are preserved instead of poisoning retrieval.
    unsupported_cases = [
        ("unsupported-01", "reliable car", ["reliability history"]),
        ("unsupported-02", "top safety pick", ["safety ratings"]),
        ("unsupported-03", "tow a 6,000 lb boat", ["towing and payload"]),
        ("unsupported-04", "needs a third row", ["seating capacity"]),
        ("unsupported-05", "Apple CarPlay and heated seats", ["installed features"]),
        ("unsupported-06", "under 40,000 miles", ["listing mileage"]),
        ("unsupported-07", "open to new or used", ["vehicle condition"]),
        ("unsupported-08", "blue exterior car", ["color"]),
        ("unsupported-09", "within 50 miles of me", ["location and distance"]),
        ("unsupported-10", "low maintenance and insurance costs", ["ownership costs"]),
        ("unsupported-11", "at least 250 miles of EV range", ["EV range and charging"]),
        ("unsupported-12", "high ground clearance", ["off-road capability"]),
        ("unsupported-13", "quiet and comfortable ride", ["ride comfort"]),
        ("unsupported-14", "payment below $400 per month", ["financing"]),
        ("unsupported-15", "clean title one-owner car", ["listing history"]),
        ("unsupported-16", "blind spot monitor and backup camera", ["installed features"]),
    ]
    for case_id, query, labels in unsupported_cases:
        expected = {"unsupported_preferences": labels}
        if case_id == "unsupported-11":
            expected["engine_fuel_type"] = "electric"
        add(case_id, query, expected, "dataset-boundary")

    # Long, multi-clause requests paraphrased from real shopping discussions.
    complex_cases = [
        (
            "complex-01",
            "Family SUV under $40k for highway road trips, at least 28 highway mpg, "
            "AWD preferred, reliable, and no Ford",
            {
                "price_max": 40000,
                "vehicle_styles": STYLE["suv"],
                "highway_mpg_min": 28,
                "preferred_driven_wheels": ["all wheel drive"],
                "excluded_makes": ["ford"],
                "ranking_preferences": ["highway_driving", "family_space"],
                "unsupported_preferences": ["reliability history"],
            },
        ),
        (
            "complex-02",
            "I want a Honda or Toyota sedan from 2014 to 2017, automatic, under "
            "$25,000, and at least 30 mpg combined",
            {
                "makes": ["honda", "toyota"],
                "vehicle_styles": ["Sedan"],
                "year_min": 2014,
                "year_max": 2017,
                "transmission_type": "AUTOMATIC",
                "price_max": 25000,
                "combined_mpg_min": 30,
            },
        ),
        (
            "complex-03",
            "Sporty manual coupe with 300+ hp; budget is 35k but I can stretch to "
            "40k; no BMW",
            {
                "transmission_type": "MANUAL",
                "vehicle_styles": ["Coupe"],
                "hp_min": 300,
                "preferred_price_max": 35000,
                "price_max": 40000,
                "excluded_makes": ["bmw"],
                "ranking_preferences": ["performance"],
            },
        ),
        (
            "complex-04",
            "Compact hatchback for a college student, preferably Toyota or Mazda, "
            "automatic, cheap to own, with a backup camera",
            {
                "vehicle_styles": STYLE["hatch"],
                "vehicle_sizes": ["Compact"],
                "preferred_makes": ["toyota", "mazda"],
                "transmission_type": "AUTOMATIC",
                "ranking_preferences": ["affordability", "compact"],
                "unsupported_preferences": ["installed features", "ownership costs"],
            },
        ),
        (
            "complex-05",
            "Midsize SUV or wagon for two kids and a dog, no minivan, good fuel "
            "economy, under 45k",
            {
                "vehicle_styles": STYLE["suv"] + ["Wagon"],
                "vehicle_sizes": ["Midsize"],
                "excluded_vehicle_styles": STYLE["minivan"],
                "price_max": 45000,
                "ranking_preferences": ["fuel_economy", "family_space", "cargo_space"],
            },
        ),
        (
            "complex-06",
            "Luxury AWD sedan, 2015 or newer, at least 350 horsepower, not electric, "
            "preferably below $55k",
            {
                "market_categories": ["Luxury"],
                "driven_wheels": ["all wheel drive"],
                "vehicle_styles": ["Sedan"],
                "year_min": 2015,
                "hp_min": 350,
                "excluded_powertrains": ["electric"],
                "preferred_price_max": 55000,
            },
        ),
        (
            "complex-07",
            "Diesel or flex-fuel 4x4 pickup between $20k and $45k with a V8",
            {
                "powertrains": ["diesel", "flex-fuel"],
                "driven_wheels": ["four wheel drive"],
                "vehicle_styles": STYLE["truck"],
                "price_min": 20000,
                "price_max": 45000,
                "engine_cylinders_min": 8,
                "engine_cylinders_max": 8,
            },
        ),
        (
            "complex-08",
            "Electric BMW or Tesla from 2013 through 2017, direct drive preferred, "
            "at least 70 combined mpg",
            {
                "makes": ["bmw", "tesla"],
                "engine_fuel_type": "electric",
                "year_min": 2013,
                "year_max": 2017,
                "combined_mpg_min": 70,
                "ranking_preferences": ["transmission:DIRECT_DRIVE"],
            },
        ),
        (
            "complex-09",
            "A reliable SUV that can tow 3,500 pounds, gets at least 25 mpg, and "
            "costs in the low 20s",
            {
                "vehicle_styles": STYLE["suv"],
                "combined_mpg_min": 25,
                "price_min": 20000,
                "price_max": 25000,
                "unsupported_preferences": ["reliability history", "towing and payload"],
            },
        ),
        (
            "complex-10",
            "No SUV or truck. I prefer a compact four-door hatchback with a manual "
            "and at least 25 city mpg",
            {
                "excluded_vehicle_styles": STYLE["suv"] + STYLE["truck"],
                "preferred_vehicle_styles": STYLE["hatch"],
                "number_of_doors_min": 4,
                "number_of_doors_max": 4,
                "preferred_vehicle_sizes": ["Compact"],
                "city_mpg_min": 25,
                "ranking_preferences": ["compact", "transmission:MANUAL"],
            },
        ),
        (
            "complex-11",
            "New or used crossover for a 35-mile commute, under $40k, hybrid if "
            "possible, but no plug-in because I cannot charge at home",
            {
                "vehicle_styles": STYLE["suv"],
                "price_max": 40000,
                "preferred_powertrains": ["hybrid"],
                "ranking_preferences": ["fuel_economy"],
                "unsupported_preferences": [
                    "vehicle condition", "EV range and charging", "plug-in capability",
                ],
            },
        ),
        (
            "complex-12",
            "Toyota Camry or Honda Accord, 2012-2016, automatic, below 30k, no more "
            "than 300 hp",
            {
                "makes": ["toyota", "honda"],
                "models": ["camry", "accord"],
                "year_min": 2012,
                "year_max": 2016,
                "transmission_type": "AUTOMATIC",
                "price_max": 30000,
                "hp_max": 300,
            },
        ),
        (
            "complex-13",
            "Fastest Porsche or Audi coupe under $80,000, newer than 2012, but "
            "nothing exotic",
            {
                "makes": ["porsche", "audi"],
                "vehicle_styles": ["Coupe"],
                "price_max": 80000,
                "year_min": 2013,
                "excluded_market_categories": ["Exotic"],
                "ranking_preferences": ["performance"],
            },
        ),
        (
            "complex-14",
            "A four-door family sedan with 30+ mpg, around $25k, safety and blind "
            "spot monitoring matter more than performance",
            {
                "number_of_doors_min": 4,
                "number_of_doors_max": 4,
                "vehicle_styles": ["Sedan"],
                "combined_mpg_min": 30,
                "preferred_price_max": 25000,
                "ranking_preferences": ["family_space"],
                "unsupported_preferences": ["safety ratings", "installed features"],
            },
        ),
        (
            "complex-15",
            "Prefer Subaru, Volvo, or Audi for winter mountain driving; must be AWD, "
            "wagon or SUV, under $50k",
            {
                "preferred_makes": ["subaru", "volvo", "audi"],
                "driven_wheels": ["all wheel drive"],
                "vehicle_styles": ["Wagon"] + STYLE["suv"],
                "price_max": 50000,
                "ranking_preferences": ["all_weather"],
            },
        ),
        (
            "complex-16",
            "Large luxury SUV with at least 6 cylinders and 300 hp, automatic, "
            "between $45k and $75k",
            {
                "vehicle_sizes": ["Large"],
                "market_categories": ["Luxury"],
                "vehicle_styles": STYLE["suv"],
                "engine_cylinders_min": 6,
                "hp_min": 300,
                "transmission_type": "AUTOMATIC",
                "price_min": 45000,
                "price_max": 75000,
            },
        ),
        (
            "complex-17",
            "Fuel-efficient daily driver: Honda, Hyundai, or Kia; sedan or hatchback; "
            "2013 or newer; under 20 grand",
            {
                "makes": ["honda", "hyundai", "kia"],
                "vehicle_styles": ["Sedan"] + STYLE["hatch"],
                "year_min": 2013,
                "price_max": 20000,
                "ranking_preferences": ["fuel_economy"],
            },
        ),
        (
            "complex-18",
            "Manual V8 coupe, rear-wheel drive, more than 400 hp, no Chevrolet, "
            "price is not important",
            {
                "transmission_type": "MANUAL",
                "engine_cylinders_min": 8,
                "engine_cylinders_max": 8,
                "vehicle_styles": ["Coupe"],
                "driven_wheels": ["rear wheel drive"],
                "hp_min": 401,
                "excluded_makes": ["chevrolet"],
            },
        ),
        (
            "complex-19",
            "Cheapest electric hatchback or compact sedan from the last five model "
            "years in this catalog",
            {
                "engine_fuel_type": "electric",
                "vehicle_styles": STYLE["hatch"] + ["Sedan"],
                "vehicle_sizes": ["Compact"],
                "year_min": 2013,
                "year_max": 2017,
                "ranking_preferences": ["compact"],
            },
        ),
        (
            "complex-20",
            "I need 4WD for snow, prefer a truck but an SUV is okay, under $35k, "
            "and I do not want diesel",
            {
                "driven_wheels": ["four wheel drive"],
                "preferred_vehicle_styles": STYLE["truck"] + STYLE["suv"],
                "price_max": 35000,
                "excluded_powertrains": ["diesel"],
                "ranking_preferences": ["all_weather"],
            },
        ),
    ]
    for case_id, query, expected in complex_cases:
        add(case_id, query, expected, "complex", "multi-constraint")

    # Broad paraphrase matrix: common make/body/budget combinations written in
    # the terse style used in inventory search boxes.
    make_style_matrix = [
        ("matrix-make-01", "Ford SUV below 35k", "ford", STYLE["suv"], 35000),
        ("matrix-make-02", "Honda sedan under $28,000", "honda", ["Sedan"], 28000),
        ("matrix-make-03", "Toyota hatchback up to 22 grand", "toyota", STYLE["hatch"], 22000),
        ("matrix-make-04", "BMW wagon no more than $55k", "bmw", ["Wagon"], 55000),
        ("matrix-make-05", "Audi coupe less than 70k", "audi", ["Coupe"], 70000),
        ("matrix-make-06", "Chevy pickup under 45 thousand", "chevrolet", STYLE["truck"], 45000),
        ("matrix-make-07", "VW convertible below $32k", "volkswagen", ["Convertible"], 32000),
        ("matrix-make-08", "Subaru SUV at most 40k", "subaru", STYLE["suv"], 40000),
        ("matrix-make-09", "Volvo sedan $50,000 or less", "volvo", ["Sedan"], 50000),
        ("matrix-make-10", "Mazda hatch <= $24k", "mazda", STYLE["hatch"], 24000),
        ("matrix-make-11", "Lexus luxury SUV under 65k", "lexus", STYLE["suv"], 65000),
        ("matrix-make-12", "Porsche performance coupe below $90k", "porsche", ["Coupe"], 90000),
        ("matrix-make-13", "Kia minivan under 30k", "kia", STYLE["minivan"], 30000),
        ("matrix-make-14", "Nissan truck no more than 38k", "nissan", STYLE["truck"], 38000),
        ("matrix-make-15", "Hyundai sedan below $21,500", "hyundai", ["Sedan"], 21500),
        ("matrix-make-16", "Cadillac convertible under 75 grand", "cadillac", ["Convertible"], 75000),
        ("matrix-make-17", "Jeep SUV maximum price of $48k", "jeep", STYLE["suv"], 48000),
        ("matrix-make-18", "Mitsubishi hatchback under $20k", "mitsubishi", STYLE["hatch"], 20000),
        ("matrix-make-19", "Buick wagon below 36k", "buick", ["Wagon"], 36000),
        ("matrix-make-20", "Infiniti coupe price limit of $52,000", "infiniti", ["Coupe"], 52000),
    ]
    for case_id, query, make, styles, maximum in make_style_matrix:
        expected = {"make": make, "vehicle_styles": styles, "price_max": maximum}
        if "luxury" in query:
            expected["market_categories"] = ["Luxury"]
        if "performance" in query:
            expected["market_categories"] = ["Performance"]
        add(case_id, query, expected, "matrix", "make", "body-style", "price")

    drivetrain_matrix = [
        ("matrix-drive-01", "AWD Toyota since 2014 under $30k", "toyota", "all wheel drive", 2014, 30000),
        ("matrix-drive-02", "4WD Ford since 2012 under $45k", "ford", "four wheel drive", 2012, 45000),
        ("matrix-drive-03", "RWD BMW since 2013 under $60k", "bmw", "rear wheel drive", 2013, 60000),
        ("matrix-drive-04", "FWD Honda since 2015 under $25k", "honda", "front wheel drive", 2015, 25000),
        ("matrix-drive-05", "all-wheel-drive Audi after 2011 below 55k", "audi", "all wheel drive", 2012, 55000),
        ("matrix-drive-06", "four wheel drive Jeep after 2010 below 40k", "jeep", "four wheel drive", 2011, 40000),
        ("matrix-drive-07", "rear-wheel-drive Lexus newer than 2012 under 50k", "lexus", "rear wheel drive", 2013, 50000),
        ("matrix-drive-08", "front wheel drive Hyundai newer than 2013 under 22k", "hyundai", "front wheel drive", 2014, 22000),
        ("matrix-drive-09", "AWD Subaru 2015 or newer under $35k", "subaru", "all wheel drive", 2015, 35000),
        ("matrix-drive-10", "4x4 Chevrolet 2011 or newer under $42k", "chevrolet", "four wheel drive", 2011, 42000),
        ("matrix-drive-11", "RWD Porsche since 2010 less than $85k", "porsche", "rear wheel drive", 2010, 85000),
        ("matrix-drive-12", "FWD Kia since 2014 less than $24k", "kia", "front wheel drive", 2014, 24000),
    ]
    for case_id, query, make, drive, year, maximum in drivetrain_matrix:
        add(case_id, query, {
            "make": make, "driven_wheels": [drive],
            "year_min": year, "price_max": maximum,
        }, "matrix", "drivetrain", "combined")

    mpg_matrix = [
        ("matrix-mpg-01", "Toyota with at least 25 mpg", "toyota", "combined_mpg_min", 25),
        ("matrix-mpg-02", "Honda with 30+ mpg", "honda", "combined_mpg_min", 30),
        ("matrix-mpg-03", "Ford with minimum 28 highway mpg", "ford", "highway_mpg_min", 28),
        ("matrix-mpg-04", "Hyundai with at least 24 city mpg", "hyundai", "city_mpg_min", 24),
        ("matrix-mpg-05", "Kia with better than 29 mpg", "kia", "combined_mpg_min", 30),
        ("matrix-mpg-06", "Mazda between 25 and 35 mpg", "mazda", "combined_range", (25, 35)),
        ("matrix-mpg-07", "Subaru under 32 mpg", "subaru", "combined_mpg_max", 31),
        ("matrix-mpg-08", "Volvo no more than 30 highway mpg", "volvo", "highway_mpg_max", 30),
        ("matrix-mpg-09", "BMW between 18 and 28 city mpg", "bmw", "city_range", (18, 28)),
        ("matrix-mpg-10", "Audi between 22 and 32 highway mpg", "audi", "highway_range", (22, 32)),
        ("matrix-mpg-11", "Nissan exactly 30 mpg", "nissan", "combined_exact", 30),
        ("matrix-mpg-12", "Chevrolet prefer 25+ mpg", "chevrolet", "preferred_combined_mpg_min", 25),
    ]
    for case_id, query, make, field, value in mpg_matrix:
        expected = {"make": make}
        if field == "combined_range":
            expected.update(combined_mpg_min=value[0], combined_mpg_max=value[1])
        elif field == "city_range":
            expected.update(city_mpg_min=value[0], city_mpg_max=value[1])
        elif field == "highway_range":
            expected.update(highway_mpg_min=value[0], highway_mpg_max=value[1])
            expected["ranking_preferences"] = ["highway_driving"]
        elif field == "combined_exact":
            expected.update(combined_mpg_min=value, combined_mpg_max=value)
        else:
            expected[field] = value
            if "highway" in field:
                expected["ranking_preferences"] = ["highway_driving"]
        add(case_id, query, expected, "matrix", "mpg")

    exclusion_matrix = [
        ("matrix-no-01", "Toyota but not a sedan", {"make": "toyota", "excluded_vehicle_styles": ["Sedan"]}),
        ("matrix-no-02", "Honda without an automatic", {"make": "honda", "excluded_transmission_types": ["AUTOMATIC"]}),
        ("matrix-no-03", "BMW but no electric models", {"make": "bmw", "excluded_powertrains": ["electric"]}),
        ("matrix-no-04", "SUV, anything but Ford", {"vehicle_styles": STYLE["suv"], "excluded_makes": ["ford"]}),
        ("matrix-no-05", "manual coupe, exclude Chevrolet", {
            "transmission_type": "MANUAL", "vehicle_styles": ["Coupe"],
            "excluded_makes": ["chevrolet"],
        }),
        ("matrix-no-06", "AWD but no luxury cars", {
            "driven_wheels": ["all wheel drive"],
            "excluded_market_categories": ["Luxury"],
        }),
        ("matrix-no-07", "wagon without diesel", {
            "vehicle_styles": ["Wagon"], "excluded_powertrains": ["diesel"],
        }),
        ("matrix-no-08", "not a minivan, prefer an SUV", {
            "excluded_vehicle_styles": STYLE["minivan"],
            "preferred_vehicle_styles": STYLE["suv"],
        }),
        ("matrix-no-09", "Honda or Mazda, no Toyota", {
            "makes": ["honda", "mazda"], "excluded_makes": ["toyota"],
        }),
        ("matrix-no-10", "automatic car but nothing exotic", {
            "transmission_type": "AUTOMATIC",
            "excluded_market_categories": ["Exotic"],
        }),
        ("matrix-no-11", "4WD truck, avoid flex-fuel", {
            "driven_wheels": ["four wheel drive"], "vehicle_styles": STYLE["truck"],
            "excluded_powertrains": ["flex-fuel"],
        }),
        ("matrix-no-12", "large SUV with no rear wheel drive", {
            "vehicle_sizes": ["Large"], "vehicle_styles": STYLE["suv"],
            "excluded_driven_wheels": ["rear wheel drive"],
        }),
    ]
    for case_id, query, expected in exclusion_matrix:
        add(case_id, query, expected, "matrix", "negation")

    # Paired hard/soft formulations ensure preference cues do not accidentally
    # become filters and "must/need" language remains enforceable.
    preference_pairs = [
        ("matrix-pref-01", "prefer AWD", {"preferred_driven_wheels": ["all wheel drive"]}),
        ("matrix-pref-02", "must have AWD", {"driven_wheels": ["all wheel drive"]}),
        ("matrix-pref-03", "prefer an SUV", {"preferred_vehicle_styles": STYLE["suv"]}),
        ("matrix-pref-04", "need an SUV", {"vehicle_styles": STYLE["suv"]}),
        ("matrix-pref-05", "prefer Toyota or Honda", {"preferred_makes": ["toyota", "honda"]}),
        ("matrix-pref-06", "Toyota or Honda only", {"makes": ["toyota", "honda"]}),
        ("matrix-pref-07", "hybrid would be nice", {"preferred_powertrains": ["hybrid"]}),
        ("matrix-pref-08", "hybrid only", {"market_categories": ["Hybrid"]}),
        ("matrix-pref-09", "luxury preferred", {"preferred_market_categories": ["Luxury"]}),
        ("matrix-pref-10", "luxury sedan", {
            "market_categories": ["Luxury"], "vehicle_styles": ["Sedan"],
        }),
        ("matrix-pref-11", "around $40k", {"preferred_price_max": 40000}),
        ("matrix-pref-12", "must stay under $40k", {"price_max": 40000}),
        ("matrix-pref-13", "2015 or newer preferred", {"preferred_year_min": 2015}),
        ("matrix-pref-14", "must be 2015 or newer", {"year_min": 2015}),
        ("matrix-pref-15", "30 mpg would be nice", {"preferred_combined_mpg_min": 30}),
        ("matrix-pref-16", "need at least 30 mpg", {"combined_mpg_min": 30}),
    ]
    for case_id, query, expected in preference_pairs:
        add(case_id, query, expected, "matrix", "hard-vs-soft")

    # Dataset-boundary combinations mirror the way real buyers bundle features.
    unsupported_matrix = [
        ("matrix-boundary-01", "reliable and safe", ["reliability history", "safety ratings"]),
        ("matrix-boundary-02", "third row with heated seats", ["seating capacity", "installed features"]),
        ("matrix-boundary-03", "tow a boat with a roomy cabin", ["towing and payload"]),
        ("matrix-boundary-04", "used car under 50k miles", ["listing mileage", "vehicle condition"]),
        ("matrix-boundary-05", "local blue SUV with CarPlay", ["installed features", "color", "location and distance"]),
        ("matrix-boundary-06", "cheap insurance and low maintenance", ["ownership costs"]),
        ("matrix-boundary-07", "EV with home charging and 300 mile range", ["EV range and charging"]),
        ("matrix-boundary-08", "off-road SUV with high ground clearance", ["off-road capability"]),
        ("matrix-boundary-09", "quiet ride and ventilated seats", ["installed features", "ride comfort"]),
        ("matrix-boundary-10", "$500 monthly payment with $3k down", ["financing"]),
        ("matrix-boundary-11", "one-owner clean-title Toyota", ["listing history"]),
        ("matrix-boundary-12", "safe family car with adaptive cruise", ["safety ratings", "installed features"]),
    ]
    for case_id, query, labels in unsupported_matrix:
        expected = {"unsupported_preferences": labels}
        if "SUV" in query:
            expected["vehicle_styles"] = STYLE["suv"]
        if "Toyota" in query:
            expected["make"] = "toyota"
        if query.startswith("EV"):
            expected["engine_fuel_type"] = "electric"
        if "family" in query:
            expected["ranking_preferences"] = ["family_space"]
        if case_id == "matrix-boundary-03":
            expected["ranking_preferences"] = ["family_space", "cargo_space"]
        if case_id == "matrix-boundary-06":
            expected["ranking_preferences"] = ["affordability"]
        if case_id == "matrix-boundary-09":
            expected["ranking_preferences"] = ["luxury"]
        add(case_id, query, expected, "matrix", "dataset-boundary")

    return cases


def main() -> None:
    base_cases = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
    base_cases = [case for case in base_cases if not case["id"].startswith("rw-")]
    for case in base_cases:
        for field in REMOVE_EXISTING_FIELDS.get(case["id"], []):
            case["expected_filters"].pop(field, None)
        case["expected_filters"].update(UPDATE_EXISTING.get(case["id"], {}))
    cases = base_cases + build_new_cases()
    QUERY_FILE.write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} labeled queries to {QUERY_FILE}")


if __name__ == "__main__":
    main()
