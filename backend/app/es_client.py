"""Shared Elasticsearch client factory."""
from functools import lru_cache

from elasticsearch import Elasticsearch

from .config import settings


@lru_cache(maxsize=1)
def get_es() -> Elasticsearch:
    """Return a cached Elasticsearch client built from settings."""
    kwargs = {"hosts": [settings.es_host]}
    if settings.es_user:
        kwargs["basic_auth"] = (settings.es_user, settings.es_password)
    return Elasticsearch(**kwargs)
