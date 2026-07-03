import { describe, expect, it } from "vitest";

import { formatOcrValidationMessage, formatOcrValidationMessages } from "./validationMessages";

describe("formatOcrValidationMessages", () => {
  it("translates known validation codes to Japanese", () => {
    expect(formatOcrValidationMessage("amount_breakdown_mismatch")).toBe(
      "金額の内訳（現金・クレジット・PAYGATE POS等）が合計と一致しません",
    );
  });

  it("joins multiple messages", () => {
    expect(formatOcrValidationMessages(["amount_breakdown_mismatch", "duplicate_receipt_candidate"])).toBe(
      "金額の内訳（現金・クレジット・PAYGATE POS等）が合計と一致しません / 同じ内容のレシートが既にある可能性があります",
    );
  });
});
