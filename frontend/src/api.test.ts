import { describe, expect, it } from "vitest";
import { formatRate, nights } from "./api";

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
