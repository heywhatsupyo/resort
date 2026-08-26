import { useEffect, useMemo, useState } from "react";
import {
  type Resort,
  type Trip,
  fetchResorts,
  fetchTrip,
  nights,
  perPerson,
  scoreOutOfTen,
  sgd,
  stayTotal,
} from "./api";

type SortKey = "value" | "price" | "score";

const SORTS: { key: SortKey; label: string }[] = [
  { key: "value", label: "Best balance" },
  { key: "price", label: "Cheapest" },
  { key: "score", label: "Best reviewed" },
];

export function App() {
  const [resorts, setResorts] = useState<Resort[]>([]);
  const [trip, setTrip] = useState<Trip | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [place, setPlace] = useState("All");
  const [sort, setSort] = useState<SortKey>("value");
  const [oneUnitOnly, setOneUnitOnly] = useState(false);

  useEffect(() => {
    Promise.all([fetchResorts(), fetchTrip()])
      .then(([nextResorts, nextTrip]) => {
        setResorts(nextResorts);
        setTrip(nextTrip);
      })
      .catch((cause: unknown) => setError(String(cause)))
      .finally(() => setLoading(false));
  }, []);

  const people = trip ? trip.adults + trip.children : 6;
  const stayNights = trip ? trip.nights : nights("2026-11-07", "2026-11-09");
  const places = useMemo(
    () => ["All", ...Array.from(new Set(resorts.map((r) => r.destination)))],
    [resorts],
  );

  const shown = useMemo(() => {
    const filtered = resorts.filter(
      (r) =>
        (place === "All" || r.destination === place) && (!oneUnitOnly || r.one_unit === 1),
    );
    const priceOf = (r: Resort) => stayTotal(r, stayNights) ?? Number.POSITIVE_INFINITY;
    const scoreOf = (r: Resort) => scoreOutOfTen(r.review_score, r.review_scale) ?? 0;

    return [...filtered].sort((a, b) => {
      if (sort === "price") return priceOf(a) - priceOf(b);
      if (sort === "score") return scoreOf(b) - scoreOf(a);
      // "value": in-budget first, then score per S$1k of stay cost.
      if (a.in_budget !== b.in_budget) return b.in_budget - a.in_budget;
      const valueOf = (r: Resort) => (scoreOf(r) || 5) / Math.max(priceOf(r) / 1000, 0.1);
      return valueOf(b) - valueOf(a);
    });
  }, [resorts, place, sort, oneUnitOnly, stayNights]);

  const cheapest = useMemo(() => {
    const priced = resorts
      .filter((r) => r.in_budget === 1)
      .map((r) => stayTotal(r, stayNights))
      .filter((v): v is number => v !== null);
    return priced.length ? Math.min(...priced) : null;
  }, [resorts, stayNights]);

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">7–9 Nov 2026 · 2 nights · ferry or car only</p>
          <h1>Where to take six people</h1>
          <p>
            {people} guests ({trip?.adults ?? 5} adults + {trip?.children ?? 1} child), three
            rooms&#39; worth of space, no flights. {resorts.length} properties compared on price and
            reviews.
          </p>
        </div>
        <span className={`pulse${error ? " is-down" : ""}`}>
          {error ? "API unreachable" : `${resorts.length} resorts loaded`}
        </span>
      </header>

      {trip?.note && (
        <p className="notice">
          <strong>Heads up:</strong> {trip.note} Your dates are the long weekend itself, so expect a
          premium on these rates and book ferries early.
        </p>
      )}

      {error && <p className="error">Could not reach the API — {error}</p>}

      <dl className="stats">
        <div className="stat">
          <dt>Nights</dt>
          <dd>{stayNights}</dd>
        </div>
        <div className="stat">
          <dt>Guests</dt>
          <dd>{people}</dd>
        </div>
        <div className="stat">
          <dt>Cheapest stay</dt>
          <dd>{cheapest === null ? "—" : sgd(cheapest)}</dd>
        </div>
        <div className="stat">
          <dt>Single-unit options</dt>
          <dd>
            {resorts.filter((r) => r.one_unit === 1 && r.in_budget === 1).length}
            <small>of {resorts.length}</small>
          </dd>
        </div>
      </dl>

      <div className="controls">
        <div className="segmented" role="group" aria-label="Filter by destination">
          {places.map((option) => (
            <button
              key={option}
              type="button"
              className={place === option ? "is-active" : ""}
              onClick={() => setPlace(option)}
            >
              {option}
            </button>
          ))}
        </div>
        <div className="segmented" role="group" aria-label="Sort order">
          {SORTS.map((option) => (
            <button
              key={option.key}
              type="button"
              className={sort === option.key ? "is-active" : ""}
              onClick={() => setSort(option.key)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <label className="toggle">
          <input
            type="checkbox"
            checked={oneUnitOnly}
            onChange={(event) => setOneUnitOnly(event.target.checked)}
          />
          All six in one unit
        </label>
      </div>

      {loading ? (
        <div className="list">
          <div className="skeleton" />
          <div className="skeleton" />
          <div className="skeleton" />
        </div>
      ) : shown.length === 0 ? (
        <p className="empty">
          Nothing matches that combination — a true 3-bedroom single unit is genuinely rare here.
        </p>
      ) : (
        <ol className="list">
          {shown.map((resort, index) => (
            <ResortCard
              key={resort.id}
              resort={resort}
              rank={index + 1}
              stayNights={stayNights}
              people={people}
            />
          ))}
        </ol>
      )}

      <footer className="foot">
        <p>
          Prices are SGD for the whole party per night, from published or average rates — not live
          quotes for 7–9 Nov 2026, because the booking sites block automated dated queries. Treat
          them as a ranking tool, then confirm each shortlisted property directly.
        </p>
      </footer>
    </div>
  );
}

function ResortCard({
  resort,
  rank,
  stayNights,
  people,
}: {
  resort: Resort;
  rank: number;
  stayNights: number;
  people: number;
}) {
  const total = stayTotal(resort, stayNights);
  const head = perPerson(total, people);
  const score = scoreOutOfTen(resort.review_score, resort.review_scale);

  return (
    <li className={`resort${resort.in_budget ? "" : " is-over"}`}>
      <div className="resort-head">
        <span className="rank">{rank}</span>
        <div>
          <h3>{resort.name}</h3>
          <p className="unit">{resort.unit}</p>
        </div>
        <div className="tags">
          <span className="chip">{resort.destination}</span>
          <span className="chip is-quiet">
            {resort.transport} · {resort.travel_time}
          </span>
          {resort.one_unit === 1 ? (
            <span className="chip is-good">One unit</span>
          ) : (
            <span className="chip is-warn">Multiple units</span>
          )}
          {resort.in_budget === 0 && <span className="chip is-bad">Over budget</span>}
        </div>
      </div>

      <div className="resort-body">
        <div className="money">
          <p className="figure">{total === null ? "—" : sgd(total)}</p>
          <p className="figure-label">
            total for {stayNights} nights
            {head !== null && <> · {sgd(head)} per person</>}
          </p>
          <p className="band">
            {resort.nightly_low === null
              ? "Rate on request"
              : resort.nightly_low === resort.nightly_high
                ? `${sgd(resort.nightly_low)} / night`
                : `${sgd(resort.nightly_low)}–${sgd(resort.nightly_high ?? resort.nightly_low)} / night`}
          </p>
        </div>

        <div className="rating">
          {score === null ? (
            <p className="no-score">No reliable review score</p>
          ) : (
            <>
              <div className="score-row">
                <strong>{score.toFixed(1)}</strong>
                <span>/ 10</span>
              </div>
              <div className="bar" aria-hidden="true">
                <span style={{ width: `${score * 10}%` }} />
              </div>
              <p className="score-meta">
                {resort.review_score}/{resort.review_scale} on {resort.review_source}
                {resort.review_count ? ` · ${resort.review_count.toLocaleString()} reviews` : ""}
              </p>
            </>
          )}
          {resort.rank_note && <p className="score-meta">{resort.rank_note}</p>}
        </div>
      </div>

      {resort.highlights && (
        <p className="note is-plus">
          <span aria-hidden="true">▲</span>
          {resort.highlights}
        </p>
      )}
      {resort.watchouts && (
        <p className="note is-minus">
          <span aria-hidden="true">▼</span>
          {resort.watchouts}
        </p>
      )}
      {resort.price_note && <p className="provenance">Price basis: {resort.price_note}</p>}
    </li>
  );
}
