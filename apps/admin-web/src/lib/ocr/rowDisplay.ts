import type { OcrExtractedRowItem } from "../../types/api";

export type OcrRowDisplayLabel = {
  key: string;
  text: string;
  tone: "warning" | "info" | "danger";
};

type OcrRowConfirmInput = Pick<
  OcrExtractedRowItem,
  | "status"
  | "source_type"
  | "terminal_id_partial"
  | "validation_errors"
  | "amount_inferred"
  | "amount_source"
  | "datetime_source"
  | "record_date"
  | "record_time"
  | "amount"
  | "transaction_no"
  | "receipt_no"
>;

const CONFIRM_BLOCKER_MESSAGES: Record<string, string> = {
  already_confirmed: "確定済みの行です",
  terminal_id_partial: "端末番号が部分抽出のため確定できません",
  validation_errors: "検証エラーを解消してから確定してください",
  amount_inferred: "金額が推定値のため、修正してから確定してください",
  missing_datetime: "日時が欠損しているため確定できません",
  missing_record_date: "日付が未入力のため確定できません",
  missing_record_time: "時刻が未入力のため確定できません",
  missing_amount: "金額が未入力のため確定できません",
  missing_transaction_no: "取引番号が未入力のため確定できません",
  missing_receipt_no: "レシート番号が未入力のため確定できません",
};

/** 確定をブロックする理由（confirm_required 単体は含めない）。 */
export function getOcrRowConfirmBlockers(row: OcrRowConfirmInput): string[] {
  const reasons: string[] = [];
  if (row.status === "confirmed") {
    reasons.push("already_confirmed");
  }
  if (row.terminal_id_partial) {
    reasons.push("terminal_id_partial");
  }
  if (row.validation_errors?.length) {
    reasons.push("validation_errors");
  }
  if (row.amount_inferred || row.amount_source === "fallback_default") {
    reasons.push("amount_inferred");
  }
  if (row.datetime_source === "missing") {
    reasons.push("missing_datetime");
  }
  if (row.source_type === "paygate_screenshot") {
    if (!row.record_date) {
      reasons.push("missing_record_date");
    }
    if (!row.record_time) {
      reasons.push("missing_record_time");
    }
    if (!row.amount) {
      reasons.push("missing_amount");
    }
    if (!row.transaction_no) {
      reasons.push("missing_transaction_no");
    }
    if (!row.receipt_no) {
      reasons.push("missing_receipt_no");
    }
  }
  return reasons;
}

export function formatOcrRowConfirmBlockerMessage(blockers: string[]): string | null {
  if (!blockers.length) {
    return null;
  }
  return blockers.map((code) => CONFIRM_BLOCKER_MESSAGES[code] || code).join(" / ");
}

/** Display labels for OCR row quality / confirm state. */
export function getOcrRowDisplayLabels(row: Pick<
  OcrExtractedRowItem,
  | "amount_inferred"
  | "amount_source"
  | "datetime_source"
  | "confirm_required"
  | "source_type"
  | "duplicate_receipt_candidate"
  | "unit_breakdown_status"
  | "reconciliation_eligible"
  | "terminal_id_partial"
  | "terminal_id_segments"
  | "voided_at"
>): OcrRowDisplayLabel[] {
  const labels: OcrRowDisplayLabel[] = [];

  if (row.voided_at) {
    labels.push({ key: "voided", text: "無効化済み", tone: "danger" });
  }

  if (row.amount_inferred) {
    labels.push({ key: "amount-inferred", text: "金額: 推定", tone: "warning" });
  } else if (row.amount_source === "corrected_ocr") {
    labels.push({ key: "amount-corrected", text: "金額: 補正", tone: "warning" });
  }

  if (row.datetime_source === "fuzzy") {
    labels.push({ key: "datetime-fuzzy", text: "日時: 要確認", tone: "warning" });
  } else if (row.datetime_source === "missing") {
    labels.push({ key: "datetime-missing", text: "日時: 欠損", tone: "danger" });
  }

  if (row.confirm_required) {
    labels.push({ key: "confirm-required", text: "要確認", tone: "info" });
  }

  if (row.terminal_id_partial) {
    labels.push({ key: "terminal-id-partial", text: "端末番号: 部分抽出", tone: "warning" });
  }

  if (row.source_type === "paygate_settlement") {
    if (row.duplicate_receipt_candidate) {
      labels.push({ key: "duplicate-candidate", text: "重複候補", tone: "warning" });
    }
  }

  return labels;
}

type OcrRowValidationInput = Pick<
  OcrExtractedRowItem,
  "status" | "source_type" | "validation_errors" | "blocking_errors" | "warnings"
>;

/** 保存データ一覧の「検証」列表示。確定済みは OK ではなく確定。 */
export function formatOcrRowValidationCell(
  row: OcrRowValidationInput,
  translateMessages: (codes: string[]) => string,
): string {
  if (row.status === "confirmed") {
    return "確定";
  }
  if (row.source_type === "paygate_settlement") {
    const messages = [...(row.blocking_errors || []), ...(row.warnings || [])];
    return messages.length ? translateMessages(messages) : "OK";
  }
  return row.validation_errors?.length ? translateMessages(row.validation_errors) : "OK";
}

/** 確定操作に使える行か（致命的欠損・推定値・検証エラーのみブロック）。 */
export function isOcrRowConfirmable(row: OcrRowConfirmInput) {
  return getOcrRowConfirmBlockers(row).length === 0;
}

/** @deprecated use isOcrRowConfirmable */
export function isOcrRowSelectable(row: OcrRowConfirmInput) {
  return isOcrRowConfirmable(row);
}

/** 保存データの削除対象にできる行か（一覧に出ている行は原則すべて削除可）。 */
export function isOcrRowDeletable(_row: Pick<OcrExtractedRowItem, "confirm_required" | "status">) {
  return true;
}
