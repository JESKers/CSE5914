# Built from the repo root so the service can import `search` and `rag`.
#   docker compose build  (context is the repo root — see docker-compose.yml)
FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# source packages (data/ is mounted as a volume at runtime)
COPY backend ./backend
COPY search ./search
COPY rag/__init__.py rag/parser.py ./rag/

RUN chmod +x /app/backend/docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]
