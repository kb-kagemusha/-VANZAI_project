import type { OcrRowEditDraft } from "../../components/ocr/OcrRowEditForm";

function stripExtension(filename: string): string {
  return filename.replace(/\.[^./\\]+$/i, "");
}

function extensionFromFilename(filename: string): string {
  const match = filename.match(/(\.[^./\\]+)$/i);
  return match?.[1] ?? ".png";
}

export function buildSettlementReceiptFilename(
  draft: Pick<OcrRowEditDraft, "terminal_short_id" | "record_date">,
  sourceFilename?: string | null,
): string {
  const shortId = draft.terminal_short_id?.trim().toLowerCase() || "unknown";
  const datePart = draft.record_date?.replace(/-/g, "") || "unknown";
  const ext = extensionFromFilename(sourceFilename || ".png");
  return `精算レシート_${shortId}_${datePart}${ext}`;
}

export function stripExtensionForDisplay(filename: string): string {
  return stripExtension(filename);
}
