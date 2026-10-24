import { describe, expect, it } from "vitest";

import {
  formatOcrRowConfirmBlockerMessage,
  formatOcrRowValidationCell,
  getOcrRowConfirmBlockers,
  getOcrRowDisplayLabels,
  isOcrRowConfirmable,
  isOcrRowDeletable,
  isOcrRowSelectable,
  matchesSavedRowStatusFilter,
  normalizeSavedRowStatusFilter,
} from "./rowDisplay";

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
    expect(labels.map((item) => item.text)).toEqual(["重複候補"]);
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
  const baseRow = {
    status: "pending_review" as const,
    source_type: "paygate_screenshot" as const,
    terminal_id_partial: false,
    validation_errors: null,
    amount_inferred: false,
    amount_source: "ocr",
    datetime_source: "ocr_strict",
    record_date: "2026-06-27",
    record_time: "12:00:00",
    amount: "980",
    transaction_no: "1272409",
    receipt_no: "7782464677325",
  };

  it("allows confirm when only confirm_required is true (OCR補正・fuzzy日時)", () => {
    expect(
      isOcrRowConfirmable({
        ...baseRow,
        amount_source: "corrected_ocr",
        datetime_source: "fuzzy",
      }),
    ).toBe(true);
  });

  it("blocks inferred amount rows", () => {
    expect(
      isOcrRowConfirmable({
        ...baseRow,
        amount_inferred: true,
        amount_source: "fallback_default",
      }),
    ).toBe(false);
  });

  it("blocks confirmed rows", () => {
    expect(isOcrRowConfirmable({ ...baseRow, status: "confirmed" })).toBe(false);
  });

  it("keeps alias isOcrRowSelectable in sync", () => {
    expect(isOcrRowSelectable({ ...baseRow, amount_inferred: true, amount_source: "fallback_default" })).toBe(
      false,
    );
  });
});

describe("isOcrRowDeletable", () => {
  it("allows deleting confirm-required rows", () => {
    expect(isOcrRowDeletable({ confirm_required: true, status: "pending_review" })).toBe(true);
    expect(isOcrRowDeletable({ confirm_required: false, status: "confirmed" })).toBe(true);
  });
});

describe("formatOcrRowValidationCell", () => {
  const translate = (codes: string[]) => codes.join(" / ");

  it("shows 確定 for confirmed rows", () => {
    expect(
      formatOcrRowValidationCell(
        { status: "confirmed", source_type: "paygate_settlement", validation_errors: [], blocking_errors: [], warnings: [] },
        translate,
      ),
    ).toBe("確定");
  });

  it("shows OK for pending settlement rows without warnings", () => {
    expect(
      formatOcrRowValidationCell(
        { status: "pending_review", source_type: "paygate_settlement", validation_errors: [], blocking_errors: [], warnings: [] },
        translate,
      ),
    ).toBe("OK");
  });
});

describe("saved row status filters", () => {
  it("normalizes legacy pending_review to unconfirmed", () => {
    expect(normalizeSavedRowStatusFilter("pending_review")).toBe("unconfirmed");
    expect(normalizeSavedRowStatusFilter("unconfirmed")).toBe("unconfirmed");
    expect(normalizeSavedRowStatusFilter("confirmed")).toBe("confirmed");
    expect(normalizeSavedRowStatusFilter("")).toBe("");
  });

  it("matches unconfirmed rows by excluding confirmed status", () => {
    expect(matchesSavedRowStatusFilter({ status: "pending_review" }, "unconfirmed")).toBe(true);
    expect(matchesSavedRowStatusFilter({ status: "parsed" }, "unconfirmed")).toBe(true);
    expect(matchesSavedRowStatusFilter({ status: "confirmed" }, "unconfirmed")).toBe(false);
    expect(matchesSavedRowStatusFilter({ status: "confirmed" }, "confirmed")).toBe(true);
    expect(matchesSavedRowStatusFilter({ status: "pending_review" }, "")).toBe(true);
  });
});
