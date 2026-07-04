import type { OcrParseProgressState } from "../lib/ocr/batchParse";

export function OcrParseProgress({ progress }: { progress: OcrParseProgressState }) {
  const percent = progress.totalImages
    ? Math.min(100, Math.round((progress.processedImages / progress.totalImages) * 100))
    : 0;
  const isActive = progress.phase === "parsing" || progress.phase === "retrying";
  const phaseLabel =
    progress.phase === "retrying"
      ? "失敗分を再試行中"
      : progress.phase === "done"
        ? "解析完了"
        : "解析中";

  return (
    <div
      className={`ocr-parse-progress${isActive ? " ocr-parse-progress--active" : ""}`}
      aria-live="polite"
    >
      <div className="ocr-parse-progress-header">
        <strong>{phaseLabel}</strong>
        <span>
          {progress.processedImages} / {progress.totalImages} 枚
        </span>
      </div>
      <div
        className={`ocr-parse-progress-bar${isActive ? " ocr-parse-progress-bar--active" : ""}`}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-busy={isActive}
        aria-label={`OCR解析の進捗 ${percent}%`}
      >
        <div
          className={`ocr-parse-progress-fill${isActive ? " ocr-parse-progress-fill--active" : ""}`}
          style={{ width: `${percent}%` }}
        />
        {isActive ? <div className="ocr-parse-progress-indeterminate" aria-hidden="true" /> : null}
      </div>
      <p className="ocr-parse-progress-meta">
        成功 {progress.successCount} / 失敗 {progress.failedCount}
        {progress.phase === "parsing" && progress.totalBatches > 0
          ? ` / バッチ ${progress.currentBatch}/${progress.totalBatches}`
          : null}
        {progress.phase === "retrying" && progress.retryImageTotal > 0
          ? ` / 再試行 ${progress.retryImageIndex}/${progress.retryImageTotal}`
          : null}
        {progress.timedOut ? " / 10分の上限に達しました" : null}
      </p>
    </div>
  );
}
