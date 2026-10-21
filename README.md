# FPLBud

FPLBud is a Fantasy Premier League assistant. Import your squad by public team ID and get transfer, captain and chip suggestions for the next gameweek, the next 3 and the next 5.

## Stack

- Frontend: Next.js (`web/`) on Vercel
- Backend: FastAPI (`api/`) on Render
- Shared Python: `fplcore/`
- Ingest: `ingest/` via GitHub Actions
- Database / auth: Supabase Postgres + Google OAuth

## Local setup

```bash
# Python (uv)
uv sync --all-packages --dev

# Database (existing Supabase project)
uv run python scripts/db_inventory.py
uv run python scripts/backup_public.py
uv run python scripts/run_sql.py db/reset_old_project.sql
uv run python scripts/run_sql.py db/schema.sql
uv run python scripts/run_sql.py db/migrations/000_backfill_profiles.sql
uv run python scripts/run_sql.py db/migrations/004_retention.sql
uv run python scripts/check_db.py

# Ingest
uv run python -m ingest.run bootstrap
uv run python -m ingest.run fixtures
uv run python -m ingest.run element_summaries
uv run python -m ingest.run metrics

# API
uv run --package api uvicorn api.main:app --reload --port 8000

# Web
cd web && pnpm install && pnpm dev
```

Copy `.env.example` to `.env` and fill in Supabase, then copy the `NEXT_PUBLIC_*` values into `web/.env.local`.

## Tests

```bash
uv run pytest -q
cd web && pnpm exec tsc --noEmit
```
