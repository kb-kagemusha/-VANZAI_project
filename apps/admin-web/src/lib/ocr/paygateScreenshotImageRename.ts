import type { OcrExtractedRowItem } from "../../types/api";

import {
  buildPaygateScreenshotFilename,
  type PaygateScreenshotFilenameRow,
} from "./paygateScreenshotFilename";

/** 同一画像の有効な PaygateSS 行（無効化除く）。 */
export function getActiveScreenshotRowsForImage(
  rows: OcrExtractedRowItem[],
  imageId: string,
): OcrExtractedRowItem[] {
  return rows.filter(
    (row) =>
      row.source_image_id === imageId &&
      row.source_type === "paygate_screenshot" &&
      !row.voided_at,
  );
}

export function rowsToScreenshotFilenameParts(
  rows: OcrExtractedRowItem[],
): PaygateScreenshotFilenameRow[] {
  return rows.map((row) => ({
    record_date: row.record_date,
    transaction_no: row.transaction_no,
  }));
}

export function isScreenshotImageFullyConfirmed(
  rows: OcrExtractedRowItem[],
  imageId: string,
): boolean {
  const active = getActiveScreenshotRowsForImage(rows, imageId);
  return active.length > 0 && active.every((row) => row.status === "confirmed");
}

export function buildSuggestedScreenshotImageFilename(
  rows: OcrExtractedRowItem[],
  imageId: string,
  sourceFilename?: string | null,
): string | null {
  const active = getActiveScreenshotRowsForImage(rows, imageId);
  if (!active.length) {
    return null;
  }
  return buildPaygateScreenshotFilename(rowsToScreenshotFilenameParts(active), sourceFilename);
}

export function isScreenshotFilenameTidy(
  rows: OcrExtractedRowItem[],
  imageId: string,
  currentFilename: string | null | undefined,
): boolean {
  if (!isScreenshotImageFullyConfirmed(rows, imageId)) {
    return true;
  }
  const suggested = buildSuggestedScreenshotImageFilename(rows, imageId, currentFilename);
  if (!suggested) {
    return true;
  }
  return (currentFilename || "").trim() === suggested;
}

export function needsScreenshotRenamePrompt(
  rows: OcrExtractedRowItem[],
  imageId: string,
  currentFilename: string | null | undefined,
): boolean {
  return (
    isScreenshotImageFullyConfirmed(rows, imageId) &&
    !isScreenshotFilenameTidy(rows, imageId, currentFilename)
  );
}

export function formatScreenshotSiblingProgressText(siblings: OcrExtractedRowItem[]): string | null {
  const active = siblings.filter((row) => !row.voided_at);
  if (active.length <= 1) {
    return null;
  }

  const confirmedCount = active.filter((row) => row.status === "confirmed").length;
  if (confirmedCount === active.length) {
    return "同一画像の取引: すべて確定済み（ファイル名の整理が可能です）";
  }

  const notConfirmed = active.filter((row) => row.status !== "confirmed");
  const needsReviewCount = notConfirmed.filter((row) => row.confirm_required).length;
  const unconfirmedOkCount = notConfirmed.length - needsReviewCount;

  const extras: string[] = [];
  if (needsReviewCount > 0) {
    extras.push(`要確認 ${needsReviewCount}件`);
  }
  if (unconfirmedOkCount > 0) {
    extras.push(`未確定 ${unconfirmedOkCount}件`);
  }

  const suffix = extras.length ? `（${extras.join(" · ")}）` : "";
  return `同一画像の取引: ${confirmedCount} / ${active.length} 件 確定済み${suffix}`;
}

export type ScreenshotRenamePromptPayload = {
  imageId: string;
  currentFilename: string;
  suggestedFilename: string;
  remainingCount: number;
};

export function buildScreenshotRenamePromptQueue(
  rows: OcrExtractedRowItem[],
  confirmedRowIds: string[],
  deferredImageIds: ReadonlySet<string>,
): ScreenshotRenamePromptPayload[] {
  const imageIds = new Set<string>();
  for (const rowId of confirmedRowIds) {
    const row = rows.find((item) => item.id === rowId);
    if (row?.source_type === "paygate_screenshot") {
      imageIds.add(row.source_image_id);
    }
  }

  const payloads: ScreenshotRenamePromptPayload[] = [];
  for (const imageId of imageIds) {
    if (deferredImageIds.has(imageId)) {
      continue;
    }
    const sample = rows.find((row) => row.source_image_id === imageId);
    const currentFilename = sample?.source_image_filename || imageId;
    if (!needsScreenshotRenamePrompt(rows, imageId, currentFilename)) {
      continue;
    }
    const suggestedFilename = buildSuggestedScreenshotImageFilename(rows, imageId, currentFilename);
    if (!suggestedFilename) {
      continue;
    }
    payloads.push({
      imageId,
      currentFilename,
      suggestedFilename,
      remainingCount: 0,
    });
  }

  return payloads.map((payload, index) => ({
    ...payload,
    remainingCount: payloads.length - index - 1,
  }));
}
