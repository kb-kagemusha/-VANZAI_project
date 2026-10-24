import { describe, expect, it } from "vitest";

import { buildParseFailureNotification } from "./parseFailureNotification";

describe("buildParseFailureNotification", () => {
  it("shows the specific error when a single image failed", () => {
    const paygateMessage =
      "正しいPaygateの画像ではありません。決済方法の記載があるスクリーンショットの画像をアップロードし直してください。";
    const notification = buildParseFailureNotification([paygateMessage], {
      successCount: 0,
      failedCount: 1,
    });

    expect(notification.message).toBe(paygateMessage);
    expect(notification.detail).toBeUndefined();
  });

  it("lists multiple failure messages in detail", () => {
    const notification = buildParseFailureNotification(["エラーA", "エラーB"], {
      successCount: 1,
      failedCount: 2,
    });

    expect(notification.message).toContain("成功 1 件");
    expect(notification.detail).toBe("エラーA\nエラーB");
  });
});
