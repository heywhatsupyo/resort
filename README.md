# resort

Monorepo: React/TypeScript frontend, FastAPI backend, file-backed SQLite database.

```
frontend/   Vite + React + TypeScript
backend/    FastAPI app + SQLite data layer
data/       resort.db lives here (gitignored)
```

## Backend

Requires Python 3.11+.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m app.db init          # create ../data/resort.db from app/schema.sql
uvicorn app.main:app --reload  # http://127.0.0.1:8000/docs
pytest
ruff check .
```

The database is a single file, `data/resort.db`. Override its location with
`RESORT_DB` (e.g. `RESORT_DB=/tmp/test.db`).

## Frontend

Requires Node 20+.

```bash
cd frontend
npm ci
npm run dev        # http://127.0.0.1:5173
npm run typecheck
npm test
npm run build
```

`/api` is proxied to the backend on port 8000 during development.

## CI

`.github/workflows/ci.yml` runs on every push and pull request to `main`:
backend (ruff + pytest on Python 3.11/3.12) and frontend (typecheck + vitest +
build on Node 20/22).
