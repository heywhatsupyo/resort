/**
 * Cloudflare Worker for the resort comparison app.
 *
 * Serves the built Vite SPA from the ASSETS binding and a read-only JSON API
 * from D1. It mirrors the read endpoints of the FastAPI backend in `backend/`,
 * so the frontend runs unchanged against either one.
 *
 * The dataset is loaded into D1 from sql/resorts_sqlite.sql, which is generated
 * from backend/app/seed_data.py — that file stays the single source of truth.
 */

interface Env {
  ASSETS: Fetcher;
  DB: D1Database;
}

const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  // The research data is public and immutable between deploys.
  "cache-control": "public, max-age=300",
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

/** Resorts, ordered so in-budget single-unit options surface first. */
async function getResorts(env: Env): Promise<Response> {
  const { results } = await env.DB.prepare(
    `SELECT * FROM resorts
     ORDER BY in_budget DESC, one_unit DESC, nightly_low`,
  ).all();
  return json(results);
}

async function getTrip(env: Env): Promise<Response> {
  const trip = await env.DB.prepare("SELECT * FROM trip LIMIT 1").first();
  return trip ? json(trip) : json({ error: "trip row missing" }, 500);
}

async function getHealth(env: Env): Promise<Response> {
  // A cheap query doubles as a D1 connectivity check.
  const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM resorts").first<{ n: number }>();
  return json({ status: "ok", store: "d1", resorts: row?.n ?? 0 });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const { pathname } = new URL(request.url);

    if (pathname.startsWith("/api/")) {
      if (request.method !== "GET" && request.method !== "HEAD") {
        return json({ error: "This deployment is read-only" }, 405);
      }

      try {
        switch (pathname) {
          case "/api/resorts":
            return await getResorts(env);
          case "/api/trip":
            return await getTrip(env);
          case "/api/health":
            return await getHealth(env);
          default:
            return json({ error: `No such endpoint: ${pathname}` }, 404);
        }
      } catch (cause) {
        // Surface the failure as JSON rather than the SPA shell, so a broken
        // binding is obvious instead of looking like an empty dataset.
        console.error("api error", pathname, cause);
        return json({ error: "Upstream query failed", detail: String(cause) }, 500);
      }
    }

    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<Env>;
