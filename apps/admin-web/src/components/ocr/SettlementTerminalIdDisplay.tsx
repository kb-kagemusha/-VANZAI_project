import type { OcrExtractedRowItem } from "../../types/api";
import { shouldShowOcrFieldConfidence } from "./OcrRowConfidenceCell";
import { OcrFieldConfidenceValue } from "./OcrFieldConfidence";

export type TerminalIdSegments = {
  eight?: string;
  four_1?: string;
  four_2?: string;
  four_3?: string;
  twelve?: string;
};

function linesFromCanonical(terminalId: string): [string, string] {
  const parts = terminalId.split("-");
  if (parts.length !== 5) {
    return [terminalId, ""];
  }
  return [`${parts[0]}-${parts[1]}-${parts[2]}`, `${parts[3]}-${parts[4]}`];
}

function linesFromSegments(segments: TerminalIdSegments): [string, string] {
  const line1 = [segments.eight, segments.four_1, segments.four_2].filter(Boolean).join("-") || "—";
  const line2 = [segments.four_3, segments.twelve].filter(Boolean).join("-") || "—";
  return [line1, line2];
}

export function formatTerminalIdDraftLines(
  terminalId: string,
  segments?: TerminalIdSegments | null,
  isPartial?: boolean,
): [string, string] {
  if (terminalId) {
    return linesFromCanonical(terminalId);
  }
  if (isPartial && segments) {
    return linesFromSegments(segments);
  }
  return ["—", ""];
}

export function SettlementTerminalIdDisplay({
  row,
  confidence,
  source,
  showPartialBadge = true,
  showConfidence = true,
  showPercent = false,
  variant = "table",
  className,
}: {
  row: Pick<OcrExtractedRowItem, "terminal_id" | "terminal_id_partial" | "terminal_id_segments" | "status">;
  confidence?: number | null;
  source?: string | null;
  showPartialBadge?: boolean;
  showConfidence?: boolean;
  showPercent?: boolean;
  variant?: "table" | "review";
  className?: string;
}) {
  const isPartial = Boolean(row.terminal_id_partial && row.terminal_id_segments);
  const effectiveConfidence = showConfidence && shouldShowOcrFieldConfidence(row) ? confidence : undefined;
  const [line1, line2] = row.terminal_id
    ? linesFromCanonical(row.terminal_id)
    : isPartial
      ? linesFromSegments(row.terminal_id_segments || {})
      : ["—", ""];

  const lines = (
    <span
      className={[
        "ocr-terminal-id-display",
        variant === "review" ? "ocr-terminal-id-display--review" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <span className="ocr-terminal-id-display-line">{line1}</span>
      {line2 && line2 !== "—" ? <span className="ocr-terminal-id-display-line">{line2}</span> : null}
    </span>
  );

  return (
    <span className="ocr-terminal-id-cell">
      {effectiveConfidence != null ? (
        <OcrFieldConfidenceValue
          value={lines}
          confidence={effectiveConfidence}
          source={source}
          showPercent={showPercent}
        />
      ) : (
        lines
      )}
      {showPartialBadge && isPartial ? (
        <button type="button" className="ocr-partial-extract-badge" disabled title="端末番号が一部のみ読み取れています。確定できません。">
          部分抽出のみ
        </button>
      ) : null}
    </span>
  );
}
