import { describe, expect, it } from "vitest";

import type { OcrExtractedRowItem } from "../../types/api";

import {
  buildScreenshotRenamePromptQueue,
  formatScreenshotSiblingProgressText,
  isScreenshotImageFullyConfirmed,
  needsScreenshotRenamePrompt,
} from "./paygateScreenshotImageRename";

function row(partial: Partial<OcrExtractedRowItem> & Pick<OcrExtractedRowItem, "id">): OcrExtractedRowItem {
  return {
    source_image_id: "img-1",
    source_image_filename: "shot.png",
    source_type: "paygate_screenshot",
    status: "parsed",
    confirm_required: false,
    voided_at: null,
    record_date: "2026-06-27",
    transaction_no: "1272409",
    parse_job_id: null,
    period_key: "202606",
    record_time: "12:00:00",
    amount: "1000",
    currency: "JPY",
    receipt_no: "1",
    payment_method: "現金",
    terminal_id: null,
    cash_sales: null,
    credit_sales: null,
    transaction_count: null,
    tax_included: null,
    subtotal: null,
    store_name: null,
    confidence: null,
    amount_inferred: false,
    amount_source: "ocr",
    datetime_source: "ocr_strict",
    manually_edited: false,
    validation_errors: null,
    project_id: null,
    report_date: null,
    linked_entity_type: null,
    linked_entity_id: null,
    confirmed_at: null,
    confirmed_by: null,
    terminal_short_id: null,
    pos_sales: null,
    other_payment: null,
    cash_unit_count: null,
    pos_unit_count: null,
    work_date: null,
    unit_breakdown_status: null,
    unit_breakdown_json: null,
    amount_ones_digit_ok: null,
    blocking_errors: null,
    warnings: null,
    duplicate_receipt_candidate: false,
    reconciliation_eligible: true,
    excluded_reason: null,
    voided_by: null,
    void_reason: null,
    branch_id: null,
    staff_id: null,
    ...partial,
  };
}

describe("paygateScreenshotImageRename", () => {
  it("detects when all active screenshot rows are confirmed", () => {
    const rows = [
      row({ id: "a", status: "confirmed" }),
      row({ id: "b", status: "confirmed", transaction_no: "1272464" }),
      row({ id: "c", voided_at: "2026-01-01T00:00:00Z" }),
    ];
    expect(isScreenshotImageFullyConfirmed(rows, "img-1")).toBe(true);
  });

  it("needs rename prompt when fully confirmed but filename differs", () => {
    const rows = [
      row({ id: "a", status: "confirmed" }),
      row({ id: "b", status: "confirmed", transaction_no: "1272464" }),
    ];
    expect(needsScreenshotRenamePrompt(rows, "img-1", "shot.png")).toBe(true);
    expect(needsScreenshotRenamePrompt(rows, "img-1", "Paygate精算画面_20260627_1272409～.png")).toBe(false);
  });

  it("formats sibling progress text", () => {
    const rows = [
      row({ id: "a", status: "confirmed" }),
      row({ id: "b", status: "parsed", confirm_required: true }),
      row({ id: "c", status: "parsed", confirm_required: false }),
    ];
    expect(formatScreenshotSiblingProgressText(rows)).toBe(
      "同一画像の取引: 1 / 3 件 確定済み（要確認 1件 · 未確定 1件）",
    );
  });

  it("builds rename prompt queue once per image", () => {
    const rows = [
      row({ id: "a", status: "confirmed" }),
      row({ id: "b", status: "confirmed", transaction_no: "1272464" }),
    ];
    const queue = buildScreenshotRenamePromptQueue(rows, ["a", "b"], new Set());
    expect(queue).toHaveLength(1);
    expect(queue[0]?.suggestedFilename).toBe("Paygate精算画面_20260627_1272409～.png");
    expect(queue[0]?.remainingCount).toBe(0);
  });
});
