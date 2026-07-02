import { describe, expect, it } from "vitest";

import { getOcrRowDisplayLabels, isOcrRowConfirmable, isOcrRowDeletable, isOcrRowSelectable } from "./rowDisplay";

const BASE_SCREENSHOT_ROW = {
  amount_inferred: false,
  amount_source: null,
  datetime_source: null,
  confirm_required: false,
  source_type: "paygate_screenshot" as const,
  duplicate_receipt_candidate: false,
  unit_breakdown_status: null,
  reconciliation_eligible: true,
  voided_at: null,
};

describe("getOcrRowDisplayLabels", () => {
  it("shows inferred amount and confirm required", () => {
    const labels = getOcrRowDisplayLabels({
      ...BASE_SCREENSHOT_ROW,
      amount_inferred: true,
      amount_source: "fallback_default",
      datetime_source: "missing",
      confirm_required: true,
    });
    expect(labels.map((item) => item.text)).toEqual(["金額: 推定", "日時: 欠損", "要確認"]);
  });

  it("shows corrected amount and fuzzy datetime", () => {
    const labels = getOcrRowDisplayLabels({
      ...BASE_SCREENSHOT_ROW,
      amount_inferred: false,
      amount_source: "corrected_ocr",
      datetime_source: "fuzzy",
      confirm_required: true,
    });
    expect(labels.map((item) => item.text)).toEqual(["金額: 補正", "日時: 要確認", "要確認"]);
  });

  it("shows voided badge first regardless of source_type", () => {
    const labels = getOcrRowDisplayLabels({ ...BASE_SCREENSHOT_ROW, voided_at: "2026-06-13T00:00:00Z" });
    expect(labels.map((item) => item.text)).toEqual(["無効化済み"]);
  });

  it("shows settlement-only badges for paygate_settlement rows", () => {
    const labels = getOcrRowDisplayLabels({
      ...BASE_SCREENSHOT_ROW,
      source_type: "paygate_settlement",
      duplicate_receipt_candidate: true,
      unit_breakdown_status: "manual",
      reconciliation_eligible: false,
    });
    expect(labels.map((item) => item.text)).toEqual(["重複候補", "単価構成要確認", "在庫照合対象外"]);
  });

  it("does not show settlement-only badges for paygate_screenshot rows", () => {
    const labels = getOcrRowDisplayLabels({
      ...BASE_SCREENSHOT_ROW,
      duplicate_receipt_candidate: true,
      unit_breakdown_status: "manual",
      reconciliation_eligible: false,
    });
    expect(labels).toEqual([]);
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
