import { useCallback, useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";

import type { OcrParseProgressState } from "../lib/ocr/batchParse";
import { OcrParseProgress } from "./OcrParseProgress";

function useParseProgressPopoverPosition(
  anchorRef: React.RefObject<HTMLElement | null>,
  visible: boolean,
) {
  const [style, setStyle] = useState<CSSProperties>({ visibility: "hidden" });

  const updatePosition = useCallback(() => {
    const anchor = anchorRef.current;
    if (!anchor) return;

    const rect = anchor.getBoundingClientRect();
    const gap = 10;
    const pad = 12;
    const width = Math.min(340, window.innerWidth - pad * 2);
    const clampLeft = (left: number) => Math.max(pad, Math.min(left, window.innerWidth - width - pad));

    const belowTop = rect.bottom + gap;
    const aboveBottom = window.innerHeight - rect.top + gap;
    const fitsBelow = belowTop + 140 <= window.innerHeight - pad;
    const fitsAbove = rect.top >= pad + 140;

    if (fitsBelow) {
      setStyle({
        position: "fixed",
        left: clampLeft(rect.left),
        top: belowTop,
        width,
        zIndex: 10000,
        visibility: "visible",
      });
      return;
    }

    if (fitsAbove) {
      setStyle({
        position: "fixed",
        left: clampLeft(rect.left),
        bottom: aboveBottom,
        top: "auto",
        width,
        zIndex: 10000,
        visibility: "visible",
      });
      return;
    }

    setStyle({
      position: "fixed",
      left: clampLeft(rect.right + gap),
      top: Math.max(pad, rect.top),
      width,
      zIndex: 10000,
      visibility: "visible",
    });
  }, [anchorRef]);

  useEffect(() => {
    if (!visible) {
      setStyle({ visibility: "hidden" });
      return;
    }

    updatePosition();
    window.addEventListener("scroll", updatePosition, true);
    window.addEventListener("resize", updatePosition);
    return () => {
      window.removeEventListener("scroll", updatePosition, true);
      window.removeEventListener("resize", updatePosition);
    };
  }, [visible, updatePosition]);

  return { style, updatePosition };
}

export function createSingleImageParseProgress(): OcrParseProgressState {
  return {
    phase: "parsing",
    totalImages: 1,
    processedImages: 0,
    successCount: 0,
    failedCount: 0,
    currentBatch: 1,
    totalBatches: 1,
    retryImageIndex: 0,
    retryImageTotal: 0,
    timedOut: false,
  };
}

type OcrParseProgressHoverProps = {
  progress: OcrParseProgressState | null;
  active: boolean;
  children: ReactNode;
  className?: string;
};

export function OcrParseProgressHover({ progress, active, children, className }: OcrParseProgressHoverProps) {
  const anchorRef = useRef<HTMLSpanElement>(null);
  const [hovering, setHovering] = useState(false);
  const isProgressActive = progress?.phase === "parsing" || progress?.phase === "retrying";
  const showPopover = Boolean(progress && hovering && active && (isProgressActive || progress.phase === "done"));
  const { style, updatePosition } = useParseProgressPopoverPosition(anchorRef, showPopover);

  useEffect(() => {
    if (showPopover) {
      updatePosition();
    }
  }, [showPopover, progress, updatePosition]);

  const popover =
    showPopover && progress ? (
      <div
        className="ocr-parse-progress-popover ocr-parse-progress-popover--portal"
        style={style}
        role="tooltip"
        onMouseEnter={() => setHovering(true)}
        onMouseLeave={() => setHovering(false)}
      >
        <OcrParseProgress progress={progress} />
      </div>
    ) : null;

  const triggerClass = [
    "ocr-parse-progress-trigger",
    active && isProgressActive ? "ocr-parse-progress-trigger--active" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <span
      ref={anchorRef}
      className={triggerClass}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      {children}
      {popover ? createPortal(popover, document.body) : null}
      {active && isProgressActive ? (
        <span className="ocr-parse-progress-trigger-hint" aria-hidden="true">
          {progress
            ? `${progress.processedImages}/${progress.totalImages}枚 · ホバーで詳細`
            : "進捗"}
        </span>
      ) : null}
    </span>
  );
}
