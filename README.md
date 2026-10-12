# FPLBud

FPLBud is a Fantasy Premier League assistant. Import your FPL squad with your team ID and get transfer, captain and chip suggestions for the next gameweek, the next 3 and the next 5, scored on custom metrics (form, fixture difficulty, home/away, expected stats, plus optional value, minutes security and price trends).

## Stack
- Frontend: Next.js (Vercel)
- Backend: Python FastAPI (pandas, PuLP/OR-Tools)
- Database: Supabase Postgres
- Scheduled ingestion: GitHub Actions

## Docs
- [Architecture](docs/ARCHITECTURE.md)
- [Database schema](db/schema.sql)
