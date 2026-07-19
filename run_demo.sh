#!/usr/bin/env bash
set -euo pipefail

# Demo-specific wrapper: runs the presentation demo inside the backend container.
cd "$(dirname "$0")"

docker compose exec -T backend python3 /app/demo_rag.py
