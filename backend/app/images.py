"""Best-effort real vehicle photos — Wikipedia lead-image thumbnails.

The catalog has no imagery, so we look up "<make> <model>" on Wikipedia and
use the article's lead image (usually a representative photo of that model).
Results are cached on disk (data/vehicle_images.json — the ./data volume, so
the cache survives container rebuilds); every make+model costs at most one
network call ever. Lookups are best-effort: on any failure we return None and
the caller simply omits the image.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_PATH = ROOT / "data" / "vehicle_images.json"
WIKI_API = "https://en.wikipedia.org/w/api.php"
THUMB_PX = 640
TIMEOUT_S = 4.0

_lock = threading.Lock()
_cache: dict[str, str | None] | None = None


def _load() -> dict[str, str | None]:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            _cache = {}
    return _cache


def _save() -> None:
    try:
        CACHE_PATH.write_text(
            json.dumps(_cache, indent=1, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass  # cache is an optimization; never fail the request over it


def _wiki_lead_image(query: str) -> str | None:
    resp = httpx.get(
        WIKI_API,
        params={
            "action": "query", "format": "json", "redirects": 1,
            "generator": "search", "gsrsearch": query, "gsrlimit": 1,
            "prop": "pageimages", "piprop": "thumbnail", "pithumbsize": THUMB_PX,
        },
        headers={"User-Agent": "JESKers-CSE5914-demo/0.1 (course project)"},
        timeout=TIMEOUT_S,
    )
    resp.raise_for_status()
    pages = (resp.json().get("query") or {}).get("pages") or {}
    for page in pages.values():
        thumb = (page.get("thumbnail") or {}).get("source")
        if thumb:
            return thumb
    return None


def image_for(make: str | None, model: str | None) -> str | None:
    """Photo URL for a make+model, or None. Cached; at most one lookup each."""
    if not make or not model:
        return None
    key = f"{make} {model}".lower().strip()
    with _lock:
        cache = _load()
        if key in cache:
            return cache[key]
    try:
        url = _wiki_lead_image(f"{make} {model}")
    except Exception:
        return None  # transient failure — don't cache, retry next time
    with _lock:
        cache[key] = url  # cache confirmed hits AND confirmed no-image answers
        _save()
    return url
