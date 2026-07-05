export type OcrFieldConfidenceTone = "high" | "medium" | "low" | "unknown";

export function getOcrFieldConfidenceTone(value: number | null | undefined): OcrFieldConfidenceTone {
  if (value == null || Number.isNaN(value)) {
    return "unknown";
  }
  if (value >= 0.97) {
    return "high";
  }
  if (value >= 0.85) {
    return "medium";
  }
  return "low";
}

export function formatOcrFieldConfidencePercent(value: number | null | undefined): string | null {
  if (value == null || Number.isNaN(value)) {
    return null;
  }
  return `${Math.round(value * 100)}%`;
}

export function getOcrFieldConfidenceClassName(tone: OcrFieldConfidenceTone): string {
  switch (tone) {
    case "high":
      return "ocr-field-confidence ocr-field-confidence--high";
    case "medium":
      return "ocr-field-confidence ocr-field-confidence--medium";
    case "low":
      return "ocr-field-confidence ocr-field-confidence--low";
    default:
      return "ocr-field-confidence";
  }
}

export const OCR_FIELD_CONFIDENCE_LEGEND = [
  { tone: "high" as const, label: "97%以上（黒）" },
  { tone: "medium" as const, label: "85–96%（青）" },
  { tone: "low" as const, label: "85%未満（オレンジ）" },
];
