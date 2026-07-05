import type { ReactNode } from "react";

import type { OcrExtractedRowItem } from "../../types/api";
import { OcrFieldConfidenceValue } from "./OcrFieldConfidence";

export function shouldShowOcrFieldConfidence(row: Pick<OcrExtractedRowItem, "status">): boolean {
  return row.status !== "confirmed";
}

export function OcrRowConfidenceCell({
  row,
  confidenceKey,
  value,
  className,
}: {
  row: Pick<OcrExtractedRowItem, "status" | "field_confidence" | "field_sources">;
  confidenceKey?: string;
  value: ReactNode;
  className?: string;
}) {
  if (!shouldShowOcrFieldConfidence(row) || !confidenceKey) {
    return <>{value}</>;
  }
  const confidence = row.field_confidence?.[confidenceKey];
  if (confidence == null) {
    return <>{value}</>;
  }
  return (
    <OcrFieldConfidenceValue
      value={value}
      confidence={confidence}
      source={row.field_sources?.[confidenceKey]}
      className={className}
    />
  );
}
