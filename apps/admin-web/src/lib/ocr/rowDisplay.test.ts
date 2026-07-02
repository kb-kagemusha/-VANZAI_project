import { describe, expect, it } from "vitest";

import { getOcrRowDisplayLabels, isOcrRowConfirmable, isOcrRowDeletable, isOcrRowSelectable } from "./rowDisplay";

describe("getOcrRowDisplayLabels", () => {
  it("shows inferred amount and confirm required", () => {
    const labels = getOcrRowDisplayLabels({
      amount_inferred: true,
      amount_source: "fallback_default",
      datetime_source: "missing",
      confirm_required: true,
    });
    expect(labels.map((item) => item.text)).toEqual(["金額: 推定", "日時: 欠損", "要確認"]);
  });

  it("shows corrected amount and fuzzy datetime", () => {
    const labels = getOcrRowDisplayLabels({
      amount_inferred: false,
      amount_source: "corrected_ocr",
      datetime_source: "fuzzy",
      confirm_required: true,
    });
    expect(labels.map((item) => item.text)).toEqual(["金額: 補正", "日時: 要確認", "要確認"]);
  });
});

describe("isOcrRowConfirmable", () => {
  it("disables confirm-required rows", () => {
    expect(isOcrRowConfirmable({ confirm_required: true, status: "pending_review" })).toBe(false);
    expect(isOcrRowConfirmable({ confirm_required: false, status: "pending_review" })).toBe(true);
    expect(isOcrRowConfirmable({ confirm_required: false, status: "confirmed" })).toBe(false);
  });

  it("keeps alias isOcrRowSelectable in sync", () => {
    expect(isOcrRowSelectable({ confirm_required: true, status: "pending_review" })).toBe(false);
  });
});

describe("isOcrRowDeletable", () => {
  it("allows deleting confirm-required rows", () => {
    expect(isOcrRowDeletable({ confirm_required: true, status: "pending_review" })).toBe(true);
    expect(isOcrRowDeletable({ confirm_required: false, status: "confirmed" })).toBe(true);
  });
});
