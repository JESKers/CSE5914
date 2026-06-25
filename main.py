"""Entry point: `uvicorn main:app --reload` serves API + frontend.

The application lives in the `app` package. This module simply re-exports the
FastAPI instance so existing tooling (docker-compose, `uvicorn main:app`) keeps
working after the pivot from Elasticsearch to the vPIC-backed SQLite catalog.
"""
from app.main import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
