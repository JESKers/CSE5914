"""Client for the NHTSA vPIC API (https://vpic.nhtsa.dot.gov/api/).

vPIC is the authoritative source for vehicle make/model/spec data. It does NOT
provide prices or rental inventory, so this app joins it with MSRP pricing from
data.csv. We use vPIC for:

  * the verified brand (make) directory                -> get_all_makes()
  * live model lookups per make/year                   -> get_models_for_make()
  * vehicle-type lookups per make                       -> get_vehicle_types_for_make()
  * VIN decoding                                         -> decode_vin()

Responses are cached in-process with a TTL so repeated calls (and the brand
directory used at startup) stay fast. All network calls degrade gracefully:
if vPIC is unreachable, callers get an empty result instead of an exception.
"""
from __future__ import annotations

import time
from threading import Lock
from typing import Any

import httpx

BASE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles"
DEFAULT_TIMEOUT = 12.0
CACHE_TTL_SECONDS = 60 * 60  # 1 hour

_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = Lock()


def _cache_get(key: str) -> Any | None:
    with _cache_lock:
        hit = _cache.get(key)
        if hit is None:
            return None
        ts, value = hit
        if time.time() - ts > CACHE_TTL_SECONDS:
            _cache.pop(key, None)
            return None
        return value


def _cache_set(key: str, value: Any) -> None:
    with _cache_lock:
        _cache[key] = (time.time(), value)


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET a vPIC endpoint and return parsed JSON, or an empty payload on error."""
    cache_key = path + "?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    query = {"format": "json", **(params or {})}
    url = f"{BASE_URL}/{path.lstrip('/')}"
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.get(url, params=query)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        return {"Count": 0, "Results": [], "_error": True}

    _cache_set(cache_key, data)
    return data


# --------------------------------------------------------------------------- #
# Public helpers
# --------------------------------------------------------------------------- #
def get_all_makes() -> list[dict[str, Any]]:
    """Return the full vPIC make directory: [{Make_ID, Make_Name}, ...]."""
    return _get("getallmakes").get("Results", [])


def make_id_index() -> dict[str, int]:
    """Map upper-cased make name -> vPIC Make_ID for fast verification/joins."""
    index: dict[str, int] = {}
    for row in get_all_makes():
        name = str(row.get("Make_Name", "")).strip().upper()
        if name and name not in index:
            index[name] = row.get("Make_ID")
    return index


def get_models_for_make(make: str, year: int | None = None) -> list[dict[str, Any]]:
    """Live model list for a make, optionally constrained to a model year."""
    if year:
        data = _get(f"GetModelsForMakeYear/make/{make}/modelyear/{year}")
    else:
        data = _get(f"GetModelsForMake/{make}")
    return data.get("Results", [])


def get_vehicle_types_for_make(make: str) -> list[dict[str, Any]]:
    """Vehicle types (Sedan, SUV, Truck, ...) vPIC associates with a make."""
    return _get(f"GetVehicleTypesForMake/{make}").get("Results", [])


def decode_vin(vin: str, year: int | None = None) -> dict[str, Any]:
    """Decode a VIN into a flat {variable: value} dict using vPIC."""
    params = {"modelyear": year} if year else None
    data = _get(f"DecodeVinValues/{vin}", params)
    results = data.get("Results", [])
    return results[0] if results else {}
