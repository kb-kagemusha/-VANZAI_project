import { describe, expect, it } from "vitest";

import {
  formatOcrImageErrorMessage,
  formatOcrValidationMessage,
  formatOcrValidationMessages,
  formatUnitBreakdownStatus,
} from "./validationMessages";

describe("formatOcrValidationMessages", () => {
  it("translates known validation codes to Japanese", () => {
    expect(formatOcrValidationMessage("amount_breakdown_mismatch")).toBe(
      "金額の内訳（現金・クレジット・PAYGATE POS等）が合計と一致しません",
    );
  });

  it("joins multiple messages", () => {
    expect(formatOcrValidationMessages(["amount_breakdown_mismatch", "duplicate_receipt_candidate"])).toBe(
      "金額の内訳（現金・クレジット・PAYGATE POS等）が合計と一致しません / 同じ内容のレシートが既にある可能性があります（重複候補）",
    );
  });

  it("translates English validation sentences from screenshot parser", () => {
    expect(formatOcrValidationMessage("record_date is missing")).toBe("日付が読み取れません");
    expect(formatOcrValidationMessage("record_time format is invalid (expected HH:MM:SS)")).toBe(
      "時刻の形式が不正です（HH:MM:SS）",
    );
  });
});

describe("formatOcrImageErrorMessage", () => {
  it("translates parse failure messages", () => {
    expect(formatOcrImageErrorMessage("No structured rows extracted")).toBe(
      "レシートから有効なデータを抽出できませんでした",
    );
    expect(formatOcrImageErrorMessage("Confirmed rows cannot be reparsed")).toBe("確定済みの行は再解析できません");
    expect(formatOcrImageErrorMessage("could not execute a primitive")).toBe(
      "画像の読み取り処理に失敗しました（OCRエンジンエラー）。画像を再アップロードするか、しばらく待ってから再解析してください。",
    );
    expect(formatOcrImageErrorMessage("Some unknown OpenCV failure")).toBe(
      "画像処理エンジンでエラーが発生しました。画像を確認して再試行してください。",
    );
    expect(formatOcrImageErrorMessage("totally unknown xyz error")).toBe(
      "画像の解析中にエラーが発生しました。再試行するか、別の画像でお試しください。",
    );
  });
});

describe("formatUnitBreakdownStatus", () => {
  it("translates unit breakdown status labels", () => {
    expect(formatUnitBreakdownStatus("ambiguous")).toBe("複数候補あり");
    expect(formatUnitBreakdownStatus(null)).toBe("-");
  });
});
