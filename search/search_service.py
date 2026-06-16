"""Search core — translate filters into Elasticsearch queries.

Owner: Kangjie. Single source of truth for how filters become ES query DSL.
Returns plain dicts so this package stays independent of the backend's API
schemas — the backend maps these into its response models.

`filters` is any object exposing the SearchFilters attributes (the backend
passes a pydantic SearchFilters; tests pass the same).
"""
from backend.app.config import settings
from backend.app.es_client import get_es

SORT_FIELDS = {
    "price": "msrp",
    "year": "year",
    "hp": "engine_hp",
    "popularity": "popularity",
}

# fields returned for each car hit
RESULT_FIELDS = [
    "make", "model", "year", "msrp", "engine_hp", "engine_fuel_type",
    "transmission_type", "vehicle_style", "highway_mpg", "city_mpg",
]


def _build_query(f) -> dict:
    must: list[dict] = []
    filt: list[dict] = []

    if f.q:
        must.append({"multi_match": {
            "query": f.q,
            "fields": ["text", "make^2", "model^2"],
            "fuzziness": "AUTO",
        }})

    for field, value in (
        ("make", f.make),
        ("model", f.model),
        ("engine_fuel_type", f.engine_fuel_type),
        ("transmission_type", f.transmission_type),
    ):
        if value:
            filt.append({"term": {field: value}})

    def _range(field, lo, hi):
        rng = {}
        if lo is not None:
            rng["gte"] = lo
        if hi is not None:
            rng["lte"] = hi
        if rng:
            filt.append({"range": {field: rng}})

    _range("year", f.year_min, f.year_max)
    _range("msrp", f.price_min, f.price_max)
    _range("engine_hp", f.hp_min, f.hp_max)

    if not must and not filt:
        return {"match_all": {}}
    return {"bool": {"must": must or {"match_all": {}}, "filter": filt}}


def search(f) -> dict:
    """Run a structured/keyword search. Returns {total, page, size, results}."""
    es = get_es()
    sort_field = SORT_FIELDS.get(f.sort, "popularity")
    body = {
        "query": _build_query(f),
        "from": (max(f.page, 1) - 1) * f.size,
        "size": f.size,
        "sort": [{sort_field: {"order": "asc" if f.order == "asc" else "desc"}}],
    }
    resp = es.search(index=settings.es_index, body=body)
    hits = resp["hits"]
    results = [
        {"id": h["_id"], **{k: h["_source"].get(k) for k in RESULT_FIELDS}}
        for h in hits["hits"]
    ]
    return {"total": hits["total"]["value"], "page": f.page, "size": f.size, "results": results}


def facets() -> dict:
    """Aggregations to drive the frontend dropdowns."""
    es = get_es()
    body = {
        "size": 0,
        "aggs": {
            "makes": {"terms": {"field": "make", "size": 100}},
            "transmissions": {"terms": {"field": "transmission_type", "size": 20}},
            "fuel_types": {"terms": {"field": "engine_fuel_type", "size": 20}},
        },
    }
    resp = es.search(index=settings.es_index, body=body)
    aggs = resp["aggregations"]

    def buckets(name):
        return [{"key": b["key"], "count": b["doc_count"]} for b in aggs[name]["buckets"]]

    return {
        "makes": buckets("makes"),
        "transmissions": buckets("transmissions"),
        "fuel_types": buckets("fuel_types"),
    }
