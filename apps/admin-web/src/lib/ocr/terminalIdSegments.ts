export const TERMINAL_ID_SEGMENT_LENGTHS = [8, 4, 4, 4, 12] as const;

export function parseTerminalIdSegments(
  value: string | null | undefined,
  segmentHints?: {
    eight?: string;
    four_1?: string;
    four_2?: string;
    four_3?: string;
    twelve?: string;
  } | null,
): string[] {
  const empty = ["", "", "", "", ""];
  const fromValue = (() => {
    if (!value) {
      return [...empty];
    }
    const normalized = value.trim().toLowerCase();
    const hyphenParts = normalized.split("-").filter((part) => part.length > 0);
    if (hyphenParts.length === 5 && hyphenParts.every((part) => /^[0-9a-f]+$/.test(part))) {
      return hyphenParts;
    }
    const hexOnly = normalized.replace(/[^0-9a-f]/g, "");
    if (hexOnly.length === 32) {
      return [
        hexOnly.slice(0, 8),
        hexOnly.slice(8, 12),
        hexOnly.slice(12, 16),
        hexOnly.slice(16, 20),
        hexOnly.slice(20, 32),
      ];
    }
    return [...empty];
  })();

  if (!segmentHints) {
    return fromValue;
  }

  return [
    fromValue[0] || segmentHints.eight || "",
    fromValue[1] || segmentHints.four_1 || "",
    fromValue[2] || segmentHints.four_2 || "",
    fromValue[3] || segmentHints.four_3 || "",
    fromValue[4] || segmentHints.twelve || "",
  ];
}

export function joinTerminalIdSegments(segments: string[]): string {
  const cleaned = segments.map((segment) => segment.toLowerCase().replace(/[^0-9a-f]/g, ""));
  if (cleaned.every((segment) => segment.length === 0)) {
    return "";
  }
  const complete = cleaned.every(
    (segment, index) => segment.length === TERMINAL_ID_SEGMENT_LENGTHS[index],
  );
  if (complete) {
    return cleaned.join("-");
  }
  return "";
}

export function isCompleteTerminalIdSegments(segments: string[]): boolean {
  return segments.every(
    (segment, index) => segment.replace(/[^0-9a-f]/gi, "").length === TERMINAL_ID_SEGMENT_LENGTHS[index],
  );
}
