FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY fplcore ./fplcore
COPY api ./api

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN uv sync --frozen --no-dev --package api

ENV PYTHONUNBUFFERED=1 \
    UV_NO_SYNC=1
EXPOSE 8000
# The venv is already synced in the image. `uv run` would rebuild the workspace
# packages on every cold start and leave the port closed long enough for a 502.
# api.serve binds $PORT (8000 only if PORT is unset) and trusts forwarded headers.
CMD ["/app/.venv/bin/python", "-m", "api.serve"]
