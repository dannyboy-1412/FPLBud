FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY fplcore ./fplcore
COPY ingest ./ingest
COPY api ./api

RUN uv sync --frozen --no-dev --package api

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uv", "run", "--package", "api", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
