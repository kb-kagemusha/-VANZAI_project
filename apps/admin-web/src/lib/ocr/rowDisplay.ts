import type { OcrExtractedRowItem } from "../../types/api";

export type OcrRowDisplayLabel = {
  key: string;
  text: string;
  tone: "warning" | "info" | "danger";
};

/** Display labels for OCR row quality / confirm state. */
export function getOcrRowDisplayLabels(row: Pick<
  OcrExtractedRowItem,
  | "amount_inferred"
  | "amount_source"
  | "datetime_source"
  | "confirm_required"
>): OcrRowDisplayLabel[] {
  const labels: OcrRowDisplayLabel[] = [];

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

  return labels;
}

/** 確定操作に使える行か（要確認・確定済みは不可）。 */
export function isOcrRowConfirmable(row: Pick<OcrExtractedRowItem, "confirm_required" | "status">) {
  return row.status !== "confirmed" && !row.confirm_required;
}

/** @deprecated use isOcrRowConfirmable */
export function isOcrRowSelectable(row: Pick<OcrExtractedRowItem, "confirm_required" | "status">) {
  return isOcrRowConfirmable(row);
}

/** 保存データの削除対象にできる行か（一覧に出ている行は原則すべて削除可）。 */
export function isOcrRowDeletable(_row: Pick<OcrExtractedRowItem, "confirm_required" | "status">) {
  return true;
}
