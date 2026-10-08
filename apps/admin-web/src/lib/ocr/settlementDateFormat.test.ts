import { describe, expect, it } from "vitest";

import { formatSettlementRecordDate } from "./settlementDateFormat";

describe("formatSettlementRecordDate", () => {
  it("formats ISO dates as YYYY/MM/DD", () => {
    expect(formatSettlementRecordDate("2026-07-04")).toBe("2026/07/04");
  });

  it("keeps slash dates", () => {
    expect(formatSettlementRecordDate("2026/07/04")).toBe("2026/07/04");
  });

  it("returns placeholder when empty", () => {
    expect(formatSettlementRecordDate(null)).toBe("ー");
  });
});
