import { describe, expect, it } from "vitest";

import { buildPaygateScreenshotFilename } from "./paygateScreenshotFilename";

describe("buildPaygateScreenshotFilename", () => {
  it("uses earliest date and smallest transaction number", () => {
    const name = buildPaygateScreenshotFilename(
      [
        { record_date: "2026-06-27", transaction_no: "1272464" },
        { record_date: "2026-06-27", transaction_no: "1272409" },
      ],
      "LINE_ALBUM.jpg",
    );
    expect(name).toBe("Paygate精算画面_20260627_1272409～.jpg");
  });

  it("reflects draft row when building from mixed sources", () => {
    const name = buildPaygateScreenshotFilename(
      [
        { record_date: "2026-06-28", transaction_no: "1272500" },
        { record_date: "2026-06-27", transaction_no: "1272463" },
      ],
      "shot.png",
    );
    expect(name).toBe("Paygate精算画面_20260627_1272463～.png");
  });
});
