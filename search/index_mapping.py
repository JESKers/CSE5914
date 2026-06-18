"""Elasticsearch index mapping for the `cars` index.

Owned by Kangjie. Tune analyzers / fields as the query layer evolves.

The `text` field uses a custom analyzer (`car_text`) that lowercases and expands
common brand nicknames so "chevy" matches "chevrolet", "vw" matches
"volkswagen", etc. Synonyms are applied at index time, so re-running the
ingest is required after editing `BRAND_SYNONYMS`.
"""

# Single-token brand nicknames -> canonical make. Index-time synonyms only need
# to be single tokens on both sides (the standard tokenizer splits on spaces and
# hyphens), which keeps the expansion unambiguous. The keyword search box hits
# the `text` field, which already contains the make, so these flow through.
BRAND_SYNONYMS = [
    "chevy, chevrolet",
    "vw, volkswagen",
    "bimmer, beemer, bmw",
    "merc, mercedes",
    "benz, mercedes",
    "vette, corvette",
    "caddy, cadillac",
    "lambo, lamborghini",
    "subie, subaru",
    "toyo, toyota",
]

CARS_MAPPING = {
    "settings": {
        "analysis": {
            "filter": {
                "car_synonyms": {
                    "type": "synonym",
                    "synonyms": BRAND_SYNONYMS,
                },
                "english_stop": {"type": "stop", "stopwords": "_english_"},
                "english_stemmer": {"type": "stemmer", "language": "english"},
            },
            "analyzer": {
                # lowercase + brand-nickname expansion + English stemming, so the
                # keyword box is forgiving ("chevy coupe" -> Chevrolet coupes).
                "car_text": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "car_synonyms", "english_stop", "english_stemmer"],
                },
            },
        }
    },
    "mappings": {
        "properties": {
            # stable unique row id, used as the sort tie-breaker for deterministic
            # pagination (ES 8.x disallows sorting on the metadata _id field).
            "id": {"type": "integer"},
            "make": {"type": "keyword"},
            "model": {"type": "keyword"},
            "year": {"type": "integer"},
            "engine_fuel_type": {"type": "keyword"},
            "engine_hp": {"type": "integer"},
            "engine_cylinders": {"type": "integer"},
            "transmission_type": {"type": "keyword"},
            "driven_wheels": {"type": "keyword"},
            "number_of_doors": {"type": "integer"},
            "market_category": {"type": "keyword"},
            "vehicle_size": {"type": "keyword"},
            "vehicle_style": {"type": "keyword"},
            "highway_mpg": {"type": "integer"},
            "city_mpg": {"type": "integer"},
            "popularity": {"type": "integer"},
            "msrp": {"type": "float"},
            # combined free-text field for the keyword search box
            "text": {"type": "text", "analyzer": "car_text"},
        }
    },
}
