#!/bin/sh
set -e

# Wait for Elasticsearch to be available.
# docker compose depends_on with service_healthy should ensure this, but wait a bit
# for the client to connect reliably.
for i in 1 2 3 4 5; do
  if python3 -c 'from backend.app.es_client import get_es; print(get_es().ping())' 2>/dev/null | grep -q True; then
    break
  fi
  echo "Elasticsearch is unavailable, retrying ($i/5)..."
  sleep 2
  if [ "$i" -eq 5 ]; then
    echo "Error: Elasticsearch is still unavailable after retries."
    exit 1
  fi
 done

if [ -f /app/data/cars_clean.json ]; then
  echo "Found /app/data/cars_clean.json. Skipping clean_data."
elif [ -f /app/data/data.csv ]; then
  echo "Generating cleaned dataset from /app/data/data.csv..."
  python3 -m search.clean_data
else
  echo "No dataset found in /app/data; creating an empty placeholder index so the API can still start."
  mkdir -p /app/data
  printf '' > /app/data/cars_clean.json
fi

echo "Checking Elasticsearch index..."
python3 - <<'PY'
import subprocess
import sys
from backend.app.config import settings
from backend.app.es_client import get_es
es = get_es()
if not es.indices.exists(index=settings.es_index):
    print(f"Index '{settings.es_index}' not found, ingesting data...")
    try:
        subprocess.check_call([sys.executable, "-m", "search.ingest"])
    except Exception as exc:
        print(f"Ingest skipped because no valid dataset was available: {exc}")
else:
    print(f"Index '{settings.es_index}' already exists, skipping ingest.")
PY

exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
