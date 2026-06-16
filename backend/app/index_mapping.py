"""Elasticsearch index mapping for the `cars` index.

Owned by Kangjie. Tune analyzers / fields as the query layer evolves.
"""

CARS_MAPPING = {
    "mappings": {
        "properties": {
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
            "text": {"type": "text", "analyzer": "english"},
        }
    }
}
