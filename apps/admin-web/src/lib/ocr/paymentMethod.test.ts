import { describe, expect, it } from "vitest";

import { formatPaygatePaymentMethodDisplay, normalizePaygatePaymentMethod } from "./paymentMethod";

describe("normalizePaygatePaymentMethod", () => {
  it("accepts allowed methods", () => {
    expect(normalizePaygatePaymentMethod("現金")).toBe("現金");
    expect(normalizePaygatePaymentMethod("QRコード")).toBe("QRコード");
    expect(normalizePaygatePaymentMethod("クレジット")).toBe("クレジット");
  });

  it("rejects invalid OCR noise", () => {
    expect(normalizePaygatePaymentMethod("現金売上")).toBeNull();
    expect(normalizePaygatePaymentMethod("その他")).toBeNull();
    expect(normalizePaygatePaymentMethod(null)).toBeNull();
  });

  it("formats display with fallback", () => {
    expect(formatPaygatePaymentMethodDisplay("現金")).toBe("現金");
    expect(formatPaygatePaymentMethodDisplay("誤認識")).toBe("ー");
    expect(formatPaygatePaymentMethodDisplay(null)).toBe("ー");
  });
});
