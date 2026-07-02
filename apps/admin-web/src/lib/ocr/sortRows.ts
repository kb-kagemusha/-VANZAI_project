import type { OcrExtractedRowItem } from "../../types/api";

export type OcrRowSortKey =
  | "source_image_filename"
  | "record_date"
  | "amount"
  | "transaction_no"
  | "receipt_no";

export type SortDirection = "asc" | "desc";

export const OCR_ROW_SORTABLE_COLUMNS: ReadonlyArray<{ key: OcrRowSortKey; label: string }> = [
  { key: "source_image_filename", label: "画像ファイル" },
  { key: "record_date", label: "日付" },
  { key: "amount", label: "金額" },
  { key: "transaction_no", label: "取引番号" },
  { key: "receipt_no", label: "レシート番号" },
];

function compareStrings(left: string | null | undefined, right: string | null | undefined) {
  return (left ?? "").localeCompare(right ?? "", "ja", { numeric: true, sensitivity: "base" });
}

function compareNumbers(left: string | null | undefined, right: string | null | undefined) {
  const leftValue = Number(left ?? 0);
  const rightValue = Number(right ?? 0);
  if (Number.isNaN(leftValue) || Number.isNaN(rightValue)) {
    return compareStrings(left, right);
  }
  return leftValue - rightValue;
}

export function sortOcrRows(
  rows: OcrExtractedRowItem[],
  sortKey: OcrRowSortKey,
  direction: SortDirection,
): OcrExtractedRowItem[] {
  const factor = direction === "asc" ? 1 : -1;
  return [...rows].sort((left, right) => {
    let result = 0;
    switch (sortKey) {
      case "source_image_filename":
        result = compareStrings(left.source_image_filename, right.source_image_filename);
        break;
      case "record_date":
        result = compareStrings(
          `${left.record_date ?? ""}T${left.record_time ?? ""}`,
          `${right.record_date ?? ""}T${right.record_time ?? ""}`,
        );
        break;
      case "amount":
        result = compareNumbers(left.amount, right.amount);
        break;
      case "transaction_no":
        result = compareStrings(left.transaction_no, right.transaction_no);
        break;
      case "receipt_no":
        result = compareStrings(left.receipt_no, right.receipt_no);
        break;
      default:
        result = 0;
    }
    if (result === 0) {
      result = compareStrings(left.id, right.id);
    }
    return result * factor;
  });
}

export function nextSortDirection(
  currentKey: OcrRowSortKey,
  nextKey: OcrRowSortKey,
  currentDirection: SortDirection,
): SortDirection {
  if (currentKey !== nextKey) {
    return "asc";
  }
  return currentDirection === "asc" ? "desc" : "asc";
}
