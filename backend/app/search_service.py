"""Search core — translate SearchFilters into Elasticsearch queries.

Owner: Kangjie. This module is the single source of truth for how filters
become ES query DSL. Refine scoring, add fuzziness, facets, etc. here.
"""
from .config import settings
from .es_client import get_es
from .schemas import (
    CarResult,
    FacetBucket,
    FacetsResponse,
    SearchFilters,
    SearchResponse,
)

SORT_FIELDS = {
    "price": "msrp",
    "year": "year",
    "hp": "engine_hp",
    "popularity": "popularity",
}


def _build_query(f: SearchFilters) -> dict:
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


def search(f: SearchFilters) -> SearchResponse:
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
        CarResult(id=h["_id"], **{
            k: h["_source"].get(k)
            for k in CarResult.model_fields
            if k != "id"
        })
        for h in hits["hits"]
    ]
    return SearchResponse(
        total=hits["total"]["value"],
        page=f.page,
        size=f.size,
        results=results,
    )


def facets() -> FacetsResponse:
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
        return [FacetBucket(key=b["key"], count=b["doc_count"]) for b in aggs[name]["buckets"]]

    return FacetsResponse(
        makes=buckets("makes"),
        transmissions=buckets("transmissions"),
        fuel_types=buckets("fuel_types"),
    )
