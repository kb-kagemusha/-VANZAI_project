import { useEffect, useMemo, useRef, useState } from "react";

import {
  isCompleteTerminalIdSegments,
  joinTerminalIdSegments,
  parseTerminalIdSegments,
  TERMINAL_ID_SEGMENT_LENGTHS,
} from "../../lib/ocr/terminalIdSegments";

const HEX_ONLY = /[^0-9a-f]/gi;

function sanitizeSegment(value: string, maxLength: number): string {
  return value.toLowerCase().replace(HEX_ONLY, "").slice(0, maxLength);
}

export function TerminalIdSegmentInput({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const [segments, setSegments] = useState(() => parseTerminalIdSegments(value));
  const lastEmitted = useRef(value);

  useEffect(() => {
    if (value !== lastEmitted.current) {
      setSegments(parseTerminalIdSegments(value));
      lastEmitted.current = value;
    }
  }, [value]);

  const emit = (nextSegments: string[]) => {
    setSegments(nextSegments);
    const joined = joinTerminalIdSegments(nextSegments);
    lastEmitted.current = joined;
    onChange(joined);
  };

  const handleChange = (index: number, nextValue: string) => {
    const maxLength = TERMINAL_ID_SEGMENT_LENGTHS[index];
    const nextSegments = [...segments];
    nextSegments[index] = sanitizeSegment(nextValue, maxLength);
    emit(nextSegments);
  };

  const complete = useMemo(() => isCompleteTerminalIdSegments(segments), [segments]);

  return (
    <div className="ocr-terminal-id-segment-input">
      <div className="ocr-terminal-id-segment-input-row">
        {[0, 1, 2].map((index) => (
          <span key={index} className="ocr-terminal-id-segment-input-group">
            <input
              type="text"
              className="ocr-terminal-id-segment-input-field"
              value={segments[index]}
              maxLength={TERMINAL_ID_SEGMENT_LENGTHS[index]}
              inputMode="text"
              autoComplete="off"
              spellCheck={false}
              disabled={disabled}
              aria-label={`端末番号 ${TERMINAL_ID_SEGMENT_LENGTHS[index]}桁`}
              onChange={(event) => handleChange(index, event.target.value)}
            />
            {index < 2 ? <span className="ocr-terminal-id-segment-input-sep">-</span> : null}
          </span>
        ))}
        <span className="ocr-terminal-id-segment-input-sep">-</span>
      </div>
      <div className="ocr-terminal-id-segment-input-row">
        {[3, 4].map((index) => (
          <span key={index} className="ocr-terminal-id-segment-input-group">
            <input
              type="text"
              className="ocr-terminal-id-segment-input-field"
              value={segments[index]}
              maxLength={TERMINAL_ID_SEGMENT_LENGTHS[index]}
              inputMode="text"
              autoComplete="off"
              spellCheck={false}
              disabled={disabled}
              aria-label={`端末番号 ${TERMINAL_ID_SEGMENT_LENGTHS[index]}桁`}
              onChange={(event) => handleChange(index, event.target.value)}
            />
            {index === 3 ? <span className="ocr-terminal-id-segment-input-sep">-</span> : null}
          </span>
        ))}
      </div>
      {!complete && segments.some((segment) => segment.length > 0) ? (
        <p className="ocr-terminal-id-segment-input-hint">各欄を 8-4-4-4-12 桁で入力してください</p>
      ) : null}
    </div>
  );
}
