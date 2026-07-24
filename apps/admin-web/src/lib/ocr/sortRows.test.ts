import { describe, expect, it } from "vitest";

import { nextSortDirection, sortOcrRows } from "./sortRows";
import type { OcrExtractedRowItem } from "../../types/api";

function row(partial: Partial<OcrExtractedRowItem>): OcrExtractedRowItem {
  return {
    id: partial.id ?? "row",
    source_type: "paygate_screenshot",
    source_image_id: "img",
    status: "pending_review",
    confirm_required: false,
    ...partial,
  } as OcrExtractedRowItem;
}

describe("sortOcrRows", () => {
  it("sorts by transaction number ascending", () => {
    const rows = [
      row({ id: "b", transaction_no: "1230557" }),
      row({ id: "a", transaction_no: "1230501" }),
    ];
    const sorted = sortOcrRows(rows, "transaction_no", "asc");
    expect(sorted.map((item) => item.transaction_no)).toEqual(["1230501", "1230557"]);
  });

  it("sorts by date descending", () => {
    const rows = [
      row({ id: "a", record_date: "2026-06-10", record_time: "19:01:20" }),
      row({ id: "b", record_date: "2026-06-10", record_time: "21:30:33" }),
    ];
    const sorted = sortOcrRows(rows, "record_date", "desc");
    expect(sorted.map((item) => item.record_time)).toEqual(["21:30:33", "19:01:20"]);
  });
});

describe("nextSortDirection", () => {
  it("resets to asc when changing column", () => {
    expect(nextSortDirection("transaction_no", "receipt_no", "desc")).toBe("asc");
  });

  it("toggles direction on same column", () => {
    expect(nextSortDirection("transaction_no", "transaction_no", "asc")).toBe("desc");
    expect(nextSortDirection("transaction_no", "transaction_no", "desc")).toBe("asc");
  });
});
