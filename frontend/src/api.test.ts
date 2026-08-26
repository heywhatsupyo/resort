import { describe, expect, it } from "vitest";
import { formatRate, midpoint, nights, perPerson, scoreOutOfTen, sgd } from "./api";

describe("formatRate", () => {
  it("renders whole dollars", () => {
    expect(formatRate(42_000)).toBe("$420.00");
  });

  it("renders cents", () => {
    expect(formatRate(1_999)).toBe("$19.99");
  });

  it("renders zero", () => {
    expect(formatRate(0)).toBe("$0.00");
  });
});

describe("nights", () => {
  it("counts whole nights", () => {
    expect(nights("2026-09-01", "2026-09-05")).toBe(4);
  });

  it("returns 0 for an empty range", () => {
    expect(nights("2026-09-01", "2026-09-01")).toBe(0);
  });

  it("returns 0 when the range is reversed", () => {
    expect(nights("2026-09-05", "2026-09-01")).toBe(0);
  });

  it("returns 0 for unparseable dates", () => {
    expect(nights("not-a-date", "2026-09-01")).toBe(0);
  });
});

describe("sgd", () => {
  it("adds thousands separators", () => {
    expect(sgd(1600)).toBe("S$1,600");
  });

  it("rounds to whole dollars", () => {
    expect(sgd(799.6)).toBe("S$800");
  });
});

describe("midpoint", () => {
  it("averages a band", () => {
    expect(midpoint(400, 600)).toBe(500);
  });

  it("falls back to whichever end exists", () => {
    expect(midpoint(null, 700)).toBe(700);
    expect(midpoint(800, null)).toBe(800);
  });

  it("is null when both ends are missing", () => {
    expect(midpoint(null, null)).toBeNull();
  });
});

describe("scoreOutOfTen", () => {
  it("rescales a /5 score", () => {
    expect(scoreOutOfTen(4, 5)).toBe(8);
  });

  it("leaves a /10 score alone", () => {
    expect(scoreOutOfTen(8.6, 10)).toBe(8.6);
  });

  it("is null without a score or scale", () => {
    expect(scoreOutOfTen(null, 10)).toBeNull();
    expect(scoreOutOfTen(9, null)).toBeNull();
  });
});

describe("perPerson", () => {
  it("splits a total", () => {
    expect(perPerson(1200, 6)).toBe(200);
  });

  it("guards against no total or no people", () => {
    expect(perPerson(null, 6)).toBeNull();
    expect(perPerson(1200, 0)).toBeNull();
  });
});
