import type { ReactNode } from "react";
import {
  formatOcrFieldConfidencePercent,
  getOcrFieldConfidenceClassName,
  getOcrFieldConfidenceTone,
  OCR_FIELD_CONFIDENCE_LEGEND,
} from "../../lib/ocr/fieldConfidence";

export function OcrFieldConfidenceLegend() {
  return (
    <div className="ocr-field-confidence-legend" aria-label="読取信憑性の目安">
      <span className="ocr-field-confidence-legend-title">読取信憑性（参考）</span>
      {OCR_FIELD_CONFIDENCE_LEGEND.map((item) => (
        <span key={item.tone} className={getOcrFieldConfidenceClassName(item.tone)}>
          {item.label}
        </span>
      ))}
    </div>
  );
}

export function OcrFieldConfidenceValue({
  value,
  confidence,
  source,
  className,
}: {
  value: ReactNode;
  confidence?: number | null;
  source?: string | null;
  className?: string;
}) {
  const tone = getOcrFieldConfidenceTone(confidence);
  const percent = formatOcrFieldConfidencePercent(confidence);
  const title = [
    percent ? `信憑性 ${percent}（参考）` : null,
    source ? `抽出: ${source}` : null,
  ]
    .filter(Boolean)
    .join(" / ");

  return (
    <span className={[getOcrFieldConfidenceClassName(tone), className].filter(Boolean).join(" ")} title={title || undefined}>
      {value}
      {percent ? <span className="ocr-field-confidence-badge">{percent}</span> : null}
    </span>
  );
}
