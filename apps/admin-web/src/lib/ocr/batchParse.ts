import type { OcrParseJobResponse, OcrSourceImageItem, OcrSourceType } from "../../types/api";

export const OCR_PARSE_SETTLEMENT_BATCH_SIZE = 6;
export const OCR_PARSE_SCREENSHOT_BATCH_SIZE = 15;
export const OCR_PARSE_OVERALL_TIMEOUT_MS = 10 * 60 * 1000;
export const OCR_PARSE_MAX_RETRIES_PER_IMAGE = 2;

export type OcrParsePhase = "parsing" | "retrying" | "done";

export type OcrParseProgressState = {
  phase: OcrParsePhase;
  totalImages: number;
  processedImages: number;
  successCount: number;
  failedCount: number;
  currentBatch: number;
  totalBatches: number;
  retryImageIndex: number;
  retryImageTotal: number;
  timedOut: boolean;
  failureMessages?: string[];
};

export type OcrBatchParseResult = {
  successCount: number;
  failedCount: number;
  rowCount: number;
  timedOut: boolean;
  failureMessages?: string[];
};

function chunkIds(ids: string[], size: number): string[][] {
  if (!ids.length) {
    return [];
  }
  const batches: string[][] = [];
  for (let index = 0; index < ids.length; index += size) {
    batches.push(ids.slice(index, index + size));
  }
  return batches;
}

export function buildOcrParseBatches(images: OcrSourceImageItem[]): string[][] {
  const settlementIds = images
    .filter((image) => image.source_type === "paygate_settlement")
    .map((image) => image.id);
  const screenshotIds = images
    .filter((image) => image.source_type === "paygate_screenshot")
    .map((image) => image.id);

  return [
    ...chunkIds(settlementIds, OCR_PARSE_SETTLEMENT_BATCH_SIZE),
    ...chunkIds(screenshotIds, OCR_PARSE_SCREENSHOT_BATCH_SIZE),
  ];
}

export function createInitialParseProgress(totalImages: number, totalBatches: number): OcrParseProgressState {
  return {
    phase: "parsing",
    totalImages,
    processedImages: 0,
    successCount: 0,
    failedCount: 0,
    currentBatch: 0,
    totalBatches,
    retryImageIndex: 0,
    retryImageTotal: 0,
    timedOut: false,
  };
}

function isTimedOut(startedAt: number, now = Date.now()): boolean {
  return now - startedAt >= OCR_PARSE_OVERALL_TIMEOUT_MS;
}

export async function runBatchedOcrParse(options: {
  images: OcrSourceImageItem[];
  parseBatch: (imageIds: string[]) => Promise<OcrParseJobResponse>;
  listRetryTargets: (imageIds: string[]) => Promise<string[]>;
  onProgress: (progress: OcrParseProgressState) => void;
  startedAt?: number;
}): Promise<OcrBatchParseResult> {
  const startedAt = options.startedAt ?? Date.now();
  const imageIds = options.images.map((image) => image.id);
  const batches = buildOcrParseBatches(options.images);
  const progress = createInitialParseProgress(imageIds.length, batches.length);

  let successCount = 0;
  let failedCount = 0;
  let rowCount = 0;

  const publish = (patch: Partial<OcrParseProgressState>) => {
    Object.assign(progress, patch);
    options.onProgress({ ...progress });
  };

  for (let batchIndex = 0; batchIndex < batches.length; batchIndex += 1) {
    if (isTimedOut(startedAt)) {
      publish({ timedOut: true, phase: "done" });
      const remaining = imageIds.length - progress.processedImages;
      return {
        successCount,
        failedCount: failedCount + Math.max(remaining, 0),
        rowCount,
        timedOut: true,
      };
    }

    const batch = batches[batchIndex];
    publish({
      phase: "parsing",
      currentBatch: batchIndex + 1,
    });

    try {
      const result = await options.parseBatch(batch);
      successCount += result.success_count;
      failedCount += result.failed_count;
      rowCount += result.row_count;
      publish({
        processedImages: progress.processedImages + batch.length,
        successCount,
        failedCount,
      });
    } catch {
      const retryTargets = await options.listRetryTargets(batch);
      const unresolvedCount = retryTargets.length || batch.length;
      failedCount += unresolvedCount;
      publish({
        processedImages: progress.processedImages + batch.length,
        successCount,
        failedCount,
      });
    }
  }

  let retryTargets = await options.listRetryTargets(imageIds);
  publish({
    phase: "retrying",
    retryImageTotal: retryTargets.length,
    retryImageIndex: 0,
  });

  for (let index = 0; index < retryTargets.length; index += 1) {
    const imageId = retryTargets[index];
    if (isTimedOut(startedAt)) {
      publish({ timedOut: true, phase: "done" });
      const remainingRetries = retryTargets.length - index;
      return {
        successCount,
        failedCount: failedCount + remainingRetries,
        rowCount,
        timedOut: true,
      };
    }

    publish({
      phase: "retrying",
      retryImageIndex: index + 1,
      retryImageTotal: retryTargets.length,
    });

    let recovered = false;
    for (let attempt = 0; attempt < OCR_PARSE_MAX_RETRIES_PER_IMAGE; attempt += 1) {
      if (isTimedOut(startedAt)) {
        publish({ timedOut: true, phase: "done" });
        const remainingRetries = retryTargets.length - index;
        return {
          successCount,
          failedCount: failedCount + remainingRetries,
          rowCount,
          timedOut: true,
        };
      }

      try {
        const result = await options.parseBatch([imageId]);
        rowCount += result.row_count;
        if (result.failed_count === 0) {
          successCount += 1;
          failedCount = Math.max(0, failedCount - 1);
          recovered = true;
          publish({
            processedImages: Math.min(progress.totalImages, progress.processedImages + 1),
            successCount,
            failedCount,
          });
          break;
        }
      } catch {
        // retry again until limit
      }
    }

    if (!recovered) {
      publish({
        processedImages: Math.min(progress.totalImages, progress.processedImages + 1),
        failedCount,
      });
    }
  }

  const finalRetryTargets = await options.listRetryTargets(imageIds);
  failedCount = Math.max(failedCount, finalRetryTargets.length);
  successCount = Math.max(0, imageIds.length - finalRetryTargets.length);

  publish({ phase: "done", timedOut: false, successCount, failedCount });
  return {
    successCount,
    failedCount,
    rowCount,
    timedOut: false,
  };
}

export function batchSizeForSourceType(sourceType: OcrSourceType): number {
  return sourceType === "paygate_settlement"
    ? OCR_PARSE_SETTLEMENT_BATCH_SIZE
    : OCR_PARSE_SCREENSHOT_BATCH_SIZE;
}
