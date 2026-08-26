// @vitest-environment jsdom
//
// The default environment in vite.config.ts is "node", which is fast and right
// for the pure helpers in api.test.ts but gives React nothing to render into.
// This docblock asks for a DOM for this file only.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { Resort, Trip } from "./api";

const TRIP: Trip = {
  check_in: "2026-11-07",
  check_out: "2026-11-09",
  nights: 2,
  adults: 5,
  children: 1,
  note: "Deepavali falls in this window.",
};

function resort(overrides: Partial<Resort> = {}): Resort {
  return {
    id: 1,
    name: "Lagoon Retreat",
    destination: "Bintan",
    transport: "Ferry",
    travel_time: "1h",
    unit: "Two 2-bedroom villas",
    bedrooms: 2,
    one_unit: 0,
    in_budget: 1,
    nightly_low: 400,
    nightly_high: 600,
    review_score: 4,
    review_scale: 5,
    review_count: 1234,
    review_source: "Booking.com",
    rank_note: null,
    highlights: "Private pool",
    watchouts: "Ferry timings are tight",
    price_note: "Published rate, Aug 2026",
    ...overrides,
  };
}

/** A fetch stub that answers by path, so the two mount requests can differ. */
function stubFetch(handler: (path: string) => unknown) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const body = await handler(String(input));
    return { ok: true, status: 200, json: async () => body } as Response;
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function stubResorts(resorts: Resort[], trip: Trip | null = TRIP) {
  return stubFetch((path) => (path === "/api/trip" ? trip : resorts));
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App on mount", () => {
  it("shows skeletons until both requests settle", async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    stubFetch(async (path) => {
      await gate;
      return path === "/api/trip" ? TRIP : [resort()];
    });

    const { container } = render(<App />);
    expect(container.querySelectorAll(".skeleton").length).toBe(3);
    expect(screen.queryByText("Lagoon Retreat")).toBeNull();

    release();
    await waitFor(() => expect(screen.getByText("Lagoon Retreat")).toBeTruthy());
    expect(container.querySelectorAll(".skeleton").length).toBe(0);
  });

  it("renders a card per resort, with the trip's party size", async () => {
    stubResorts([resort(), resort({ id: 2, name: "Cliff House", destination: "Batam" })]);

    render(<App />);
    await waitFor(() => expect(screen.getByText("Lagoon Retreat")).toBeTruthy());

    expect(screen.getByText("Cliff House")).toBeTruthy();
    expect(screen.getAllByRole("listitem").length).toBe(2);
    expect(screen.getByText("2 resorts loaded")).toBeTruthy();
    // 5 adults + 1 child, read from /api/trip rather than the hardcoded fallback.
    expect(screen.getByText(/6 guests \(5 adults \+ 1 child\)/)).toBeTruthy();
  });

  it("requests both endpoints exactly once", async () => {
    const fetchMock = stubResorts([resort()]);

    render(<App />);
    await waitFor(() => expect(screen.getByText("Lagoon Retreat")).toBeTruthy());

    expect(fetchMock.mock.calls.map((call) => String(call[0])).sort()).toEqual([
      "/api/resorts",
      "/api/trip",
    ]);
  });

  it("shows the trip note when the API sends one", async () => {
    stubResorts([resort()]);

    render(<App />);
    await waitFor(() => expect(screen.getByText(/Deepavali falls in this window/)).toBeTruthy());
  });
});

describe("App when the API is unreachable", () => {
  it("reports the failure instead of an empty shortlist", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("network down");
      }),
    );

    render(<App />);
    await waitFor(() => expect(screen.getByText("API unreachable")).toBeTruthy());

    expect(screen.getByText(/Could not reach the API/)).toBeTruthy();
    expect(screen.getByText("network down", { exact: false })).toBeTruthy();
    // Pins today's behaviour rather than endorsing it: with no resorts loaded,
    // the list also falls through to its "nothing matched your filters" copy,
    // so a failed request currently reads as an empty result set as well as an
    // error. Worth separating, but that is a UI change, not a test change.
    expect(screen.getByText(/Nothing matches that combination/)).toBeTruthy();
  });

  it("reports a non-ok response, not just a rejected request", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 503, json: async () => ({}) }) as Response),
    );

    render(<App />);
    await waitFor(() => expect(screen.getByText(/Could not reach the API/)).toBeTruthy());
    expect(screen.getByText(/responded 503/)).toBeTruthy();
  });
});

describe("App filters", () => {
  it("narrows the list to one destination", async () => {
    stubResorts([resort(), resort({ id: 2, name: "Cliff House", destination: "Batam" })]);

    render(<App />);
    await waitFor(() => expect(screen.getAllByRole("listitem").length).toBe(2));

    fireEvent.click(screen.getByRole("button", { name: "Batam" }));
    expect(screen.getAllByRole("listitem").length).toBe(1);
    expect(screen.getByText("Cliff House")).toBeTruthy();
    expect(screen.queryByText("Lagoon Retreat")).toBeNull();
  });

  it("shows the empty state when nothing matches", async () => {
    stubResorts([resort({ one_unit: 0 })]);

    render(<App />);
    await waitFor(() => expect(screen.getByText("Lagoon Retreat")).toBeTruthy());

    fireEvent.click(screen.getByLabelText(/All six in one unit/));
    expect(screen.getByText(/Nothing matches that combination/)).toBeTruthy();
    expect(screen.queryByRole("listitem")).toBeNull();
  });

  it("reorders by price when asked", async () => {
    stubResorts([
      resort({ id: 1, name: "Pricey", nightly_low: 900, nightly_high: 900 }),
      resort({ id: 2, name: "Cheap", nightly_low: 100, nightly_high: 100 }),
    ]);

    render(<App />);
    await waitFor(() => expect(screen.getAllByRole("listitem").length).toBe(2));

    fireEvent.click(screen.getByRole("button", { name: "Cheapest" }));
    const names = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(names).toEqual(["Cheap", "Pricey"]);
  });
});
