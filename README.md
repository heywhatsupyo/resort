# resort

A small full-stack app that compares resorts for one specific trip: **six people,
7–9 November 2026, leaving Singapore without flying.**

It exists because the trip has an awkward set of constraints, and comparing
options by hand across a dozen booking sites was a mess. The app holds the
research as structured data, serves it over an API, and renders it as a sortable
comparison with prices and review scores side by side.

```
frontend/   Vite + React + TypeScript — the comparison UI
backend/    FastAPI + SQLite — the API and the researched dataset
sql/        Portable .sql dumps of the dataset (SQLite + MySQL)
data/       resort.db lives here (gitignored)
```

## The trip

| Constraint | Value |
|---|---|
| Dates | 7–9 Nov 2026 (2 nights, Sat–Mon) |
| Party | 5 adults + one 5-year-old = 6 people |
| Space needed | 3 rooms' worth |
| Togetherness | Everyone in one property; ideally one unit |
| Travel | **No flights** — ferry or car only |
| Budget | Roughly S$1,050–1,800 per night for the whole party |
| Destinations | Bintan and Batam (ferry), Desaru/Johor (car) |

Two findings shaped everything else:

**1. The dates are the Deepavali long weekend.** Deepavali falls on Sunday
8 Nov 2026, with the holiday-in-lieu on Monday 9 Nov. So these are peak dates —
expect a premium over every rate below, book ferries early, and if you drive to
Desaru, expect the Saturday-morning Tuas queue to add hours.

**2. A true 3-bedroom villa is rare here.** Most of the best-reviewed resorts
simply do not have one:

- Banyan Tree Bintan tops out at a 2-bedroom villa
- Angsana Bintan (now Homm Laguna Bintan) tops out at a 2-bedroom family suite
- Cassia Bintan has 1- and 2-bedroom apartments only
- Montigo Nongsa jumps straight from 2-bedroom to 4-bedroom
- The Westin Desaru is rooms only

That leaves genuine single-unit options at Nirwana Gardens (Indra Maya, Banyu
Biru), Anantara Desaru's residences, Montigo's oversized 4-bedroom, and
out-of-budget places like The Sanchaya. The app flags this with a `one_unit` field
and an "All six in one unit" filter, so the cost of insisting on it is visible.

## The shortlist

Totals are for 2 nights for the whole party, from the midpoint of each price band.
Review scores are normalised to /10 so different sources can be compared.

| Resort | Where | Unit for six | 2 nights | Review |
|---|---|---|---|---|
| Turi Beach | Batam, ferry | 3 rooms | S$450 | 8.0 (2,296) · #27 of 144 |
| HARRIS Barelang | Batam, ferry | 3 rooms | S$540 | — |
| Cassia Bintan | Bintan, ferry | 2BR + 1BR apartments | S$980 | 8.0 (2,388) · **#1 of 53** |
| Angsana / Homm Laguna | Bintan, ferry | 2BR suite + room | S$1,000 | 8.4 |
| Nirwana Banyu Biru | Bintan, ferry | **3BR villa** | S$1,150 | no data |
| Hard Rock Desaru | Johor, car | 3 connecting rooms | S$1,170 | 8.6 · **#1 of 11** |
| The Westin Desaru | Johor, car | 3 rooms | S$1,440 | — |
| Nirwana Indra Maya | Bintan, ferry | **3BR villa, sleeps 6** | S$1,600 | 8.0 (166) · #13 of 16 |
| Montigo Nongsa | Batam, ferry | **4BR residence** | S$2,000 | 8.0 (5,363) · #14 of 144 |
| Banyan Tree Bintan | Bintan, ferry | 2BR villa + villa | S$2,500 | **9.0** (140) |
| Anantara Desaru | Johor, car | **3BR residence** | S$4,000 | 518 reviews, family-strong |
| The Sanchaya | Bintan, ferry | 3BR villa | S$9,000 | over budget, for reference |

The headline trade-off: **Cassia Bintan is ranked #1 of 53 in Lagoi at about
S$980** across two apartments, while **Indra Maya's 3-bedroom villa costs about
S$1,600 and ranks #13 of 16**. Insisting on a single unit costs roughly S$600 and
a meaningful drop in quality.

## Data provenance — please read

**The prices are indicative published or average rates, not live quotes for
7–9 Nov 2026.** Booking.com, Agoda, Klook and several resort sites block
automated dated queries, so live availability for these specific dates could not
be retrieved programmatically. The bands for Banyu Biru, Anantara's 3-bedroom
residence and Montigo's 4-bedroom are explicitly estimates.

Every record carries a `price_note` explaining what its number is based on, and
the UI shows it on each card. Use this to rank and shortlist, then get direct
quotes before booking. Review scores and rankings are as published by
Tripadvisor, Booking.com, Trip.com and Kayak at the time of research
(August 2026).

## Running it

### Backend — requires Python 3.11+

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m app.db seed                # create data/resort.db and load the shortlist
uvicorn app.main:app --reload        # http://127.0.0.1:8000/docs
```

The database is one file, `data/resort.db`. Override its location with the
`RESORT_DB` environment variable, which `db_path()` reads from the process
environment — there is no `.env` loader, so export it or set it per command:

```bash
cd backend
RESORT_DB=../data/other.db python -m app.db init
RESORT_DB=../data/other.db uvicorn app.main:app --reload
```

Relative paths resolve against the working directory, so from `backend/` the
repo's own database is `../data/resort.db`. An absolute path avoids the
question. (Note that the Worker deployment does not use this at all — it reads
resorts from a D1 binding; see “Deploying to Cloudflare” below.)

The app seeds itself on startup, so `python -m app.db seed` is only needed if you
want the database populated without running the server.

| Endpoint | Returns |
|---|---|
| `GET /api/resorts` | The shortlist, in-budget and single-unit options first |
| `GET /api/trip` | Trip dates, party size, the Deepavali note |
| `GET /api/health` | Liveness, and whether the database answers |
| `GET /api/rooms`, `GET /api/bookings` | Booking tables from the original scaffold |
| `POST /api/rooms`, `/api/guests`, `/api/bookings` | Create a room, guest or booking |

A room cannot hold two overlapping stays. A stay is the half-open interval
`[check_in, check_out)`, so a checkout and a check-in on the same day are fine
and `POST /api/bookings` returns **409** for anything that genuinely overlaps.
The rule is a trigger in `schema.sql` rather than a check in the API, so two
concurrent requests cannot both pass it.

### Frontend — requires Node 20.19+, 22.13+ or 24+

```bash
cd frontend
npm ci
npm run dev        # http://127.0.0.1:5173
```

`/api` is proxied to the backend on port 8000 in development, so run both.

### Tests

```bash
cd backend  && pytest && ruff check .
cd frontend && npm run typecheck && npm test && npm run build
```

Frontend tests run in Vitest's `node` environment by default, which the pure
helpers in `api.test.ts` don't need a DOM for. Files that render components opt
into jsdom with a `// @vitest-environment jsdom` docblock, as `App.test.tsx`
does. `jsdom` is held at 29.x deliberately: 30.x requires Node 22.22+, and CI
covers Node 20.

## The SQL files

`sql/` holds the dataset as portable SQL, for using the data outside this app:

```bash
sqlite3 mytrip.db < sql/resorts_sqlite.sql   # SQLite
mysql mydatabase  < sql/resorts_mysql.sql    # MySQL / MariaDB
```

Both are generated from the same source, so don't edit them by hand — edit
`backend/app/seed_data.py` and regenerate:

```bash
cd backend && python scripts/export_sql.py
```

## Changing the research

`backend/app/seed_data.py` is the single source of truth for the shortlist. Add or
edit an entry there, then:

1. `python scripts/export_sql.py` to refresh the SQL dumps
2. Restart the backend (it re-seeds on startup; seeding is idempotent)

The tests assert that every resort has a destination, a unit description,
highlights, watch-outs and a price basis — so an incomplete entry fails CI rather
than showing up as a blank card.

## Deploying to Cloudflare

The app deploys as a single Cloudflare Worker: the built SPA is served from
static assets, and `/api/*` is served by `worker/index.ts` reading from **D1**.
Cloudflare has no writable filesystem, so the local SQLite file cannot come
along — D1 replaces it, loaded from the same generated `sql/resorts_sqlite.sql`.

`worker/index.ts` mirrors only the *read* endpoints (`/api/resorts`, `/api/trip`,
`/api/health`); the deployment is read-only and returns 405 for writes. The
frontend is unchanged, because the Worker serves the assets and the API on one
origin.

**Requires Node 22+** (wrangler's minimum). If your default `node` is older:

```bash
brew install node@22
export PATH="/usr/local/opt/node@22/bin:$PATH"
```

### First deploy

```bash
npm install
npx wrangler login                                    # opens a browser
npx wrangler d1 create resort                         # copy the database_id it prints
#   paste that id into wrangler.jsonc -> d1_databases[0].database_id
npm run db:import                                     # load the shortlist into D1
npm run deploy                                        # builds the SPA, then deploys
```

`npm run deploy` prints the live `*.workers.dev` URL. Verify with:

```bash
curl https://<your-worker>.workers.dev/api/health     # {"status":"ok","store":"d1",...}
```

### Redeploying

```bash
npm run deploy       # code or UI changes
npm run db:import    # after editing backend/app/seed_data.py + export_sql.py
```

`db:import` re-runs the dump, which begins with `DROP TABLE IF EXISTS`, so it
replaces the data rather than duplicating it.

### Local preview against real D1

```bash
npx wrangler dev     # http://localhost:8787, Worker + assets together
```

Note this is a different setup from `npm run dev` in `frontend/`, which proxies
to the local FastAPI backend. Both work; the Worker path is what production runs.

## CI

`.github/workflows/ci.yml` runs on every push and pull request to `main`:

- **backend** on Python 3.11 and 3.12 — `ruff check`, `ruff format --check`,
  `pytest`, plus a smoke test that builds the database from `schema.sql`
- **frontend** on Node 20 and 22 — `tsc --noEmit`, `vitest`, `vite build`, and
  uploads `dist/` as an artifact
