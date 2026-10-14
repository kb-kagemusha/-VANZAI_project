import { describe, expect, it } from "vitest";

import { formatCurrency, formatYenAmountPlain, normalizeYenAmount } from "./index";

describe("normalizeYenAmount", () => {
  it("rounds decimal strings to integer yen", () => {
    expect(normalizeYenAmount("5880.00")).toBe(5880);
    expect(normalizeYenAmount("980.50")).toBe(981);
  });
});

describe("formatCurrency", () => {
  it("does not show decimal places for yen", () => {
    expect(formatCurrency("5880.00")).toBe("￥5,880");
    expect(formatCurrency(980)).toBe("￥980");
  });
});

describe("formatYenAmountPlain", () => {
  it("returns integer string without decimals", () => {
    expect(formatYenAmountPlain("5880.00")).toBe("5880");
  });
});
