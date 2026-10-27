import { describe, expect, it, vi } from "vitest";

import {
  OCR_PARSE_MAX_RETRIES_PER_IMAGE,
  OCR_PARSE_OVERALL_TIMEOUT_MS,
  OCR_PARSE_SETTLEMENT_BATCH_SIZE,
  OCR_PARSE_SCREENSHOT_BATCH_SIZE,
  buildOcrParseBatches,
  runBatchedOcrParse,
} from "./batchParse";
import type { OcrSourceImageItem } from "../../types/api";

function image(id: string, sourceType: OcrSourceImageItem["source_type"]): OcrSourceImageItem {
  return {
    id,
    source_type: sourceType,
    original_filename: `${id}.jpg`,
    sha256: id,
    mime_type: "image/jpeg",
    size_bytes: 1000,
    period_key: null,
    parse_status: "pending",
    uploaded_by: "tester",
    last_job_id: null,
    error_message: null,
    created_at: "2026-07-04T00:00:00Z",
  };
}

describe("buildOcrParseBatches", () => {
  it("splits settlement into batches of 6 and screenshots into batches of 15", () => {
    const images = [
      ...Array.from({ length: 20 }, (_, index) => image(`s-${index}`, "paygate_settlement")),
      ...Array.from({ length: 20 }, (_, index) => image(`p-${index}`, "paygate_screenshot")),
    ];

    const batches = buildOcrParseBatches(images);
    expect(batches).toHaveLength(4 + 2);
    expect(batches[0]).toHaveLength(OCR_PARSE_SETTLEMENT_BATCH_SIZE);
    expect(batches[3]).toHaveLength(2);
    expect(batches[4]).toHaveLength(OCR_PARSE_SCREENSHOT_BATCH_SIZE);
    expect(batches[5]).toHaveLength(5);
  });
});

describe("runBatchedOcrParse", () => {
  it("runs batches sequentially and retries failed images individually", async () => {
    const images = [image("s-1", "paygate_settlement"), image("p-1", "paygate_screenshot")];
    const parseBatch = vi
      .fn()
      .mockResolvedValueOnce({ success_count: 1, failed_count: 1, row_count: 1 })
      .mockResolvedValueOnce({ success_count: 1, failed_count: 0, row_count: 1 })
      .mockResolvedValueOnce({ success_count: 1, failed_count: 0, row_count: 1 });
    const listRetryTargets = vi
      .fn()
      .mockResolvedValueOnce(["s-1"])
      .mockResolvedValueOnce([]);

    const progressSnapshots: number[] = [];
    const result = await runBatchedOcrParse({
      images,
      parseBatch,
      listRetryTargets,
      onProgress: (progress) => {
        progressSnapshots.push(progress.processedImages);
      },
    });

    expect(parseBatch).toHaveBeenCalledTimes(3);
    expect(parseBatch.mock.calls[2]?.[0]).toEqual(["s-1"]);
    expect(result.successCount).toBe(2);
    expect(result.failedCount).toBe(0);
    expect(result.rowCount).toBe(3);
    expect(progressSnapshots.at(-1)).toBe(2);
  });

  it("stops when the overall timeout is reached", async () => {
    const images = Array.from({ length: 3 }, (_, index) => image(`s-${index}`, "paygate_settlement"));
    const parseBatch = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          setTimeout(
            () => resolve({ success_count: 1, failed_count: 0, row_count: 1 }),
            20,
          );
        }),
    );

    const result = await runBatchedOcrParse({
      images,
      parseBatch,
      listRetryTargets: async () => [],
      startedAt: Date.now() - OCR_PARSE_OVERALL_TIMEOUT_MS,
      onProgress: () => undefined,
    });

    expect(parseBatch).not.toHaveBeenCalled();
    expect(result.timedOut).toBe(true);
  });
});

describe("retry constants", () => {
  it("uses the agreed retry and timeout defaults", () => {
    expect(OCR_PARSE_MAX_RETRIES_PER_IMAGE).toBe(2);
    expect(OCR_PARSE_OVERALL_TIMEOUT_MS).toBe(600_000);
  });
});
