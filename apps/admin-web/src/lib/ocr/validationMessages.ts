/** OCR 検証コード → 日本語メッセージ */
const OCR_VALIDATION_MESSAGE_JA: Record<string, string> = {
  amount_breakdown_mismatch:
    "金額の内訳（現金・クレジット・PAYGATE POS等）が合計と一致しません",
  settlement_amount_missing: "合計金額が読み取れません",
  transaction_count_invalid: "通常取引数が不正です",
  missing_terminal_short_id: "端末識別番号が読み取れません（4桁）",
  invalid_terminal_short_id: "端末識別番号は4桁の16進（0-9a-f）で入力してください",
  amount_ones_digit_invalid: "合計金額の1の位が不正です（10円単位ではありません）",
  cash_sales_ones_digit_invalid: "現金売上の1の位が不正です（10円単位ではありません）",
  pos_sales_ones_digit_invalid: "PAYGATE POS売上の1の位が不正です（10円単位ではありません）",
  pos_sales_unit_invalid:
    "PAYGATE POS売上が不正です（¥980/¥1,480/¥2,980の組み合わせではありません）",
  cash_sales_unit_invalid:
    "現金売上が不正です（¥980/¥1,480/¥2,980の組み合わせではありません）",
  credit_sales_ones_digit_invalid: "クレジット売上の1の位が不正です（10円単位ではありません）",
  other_payment_ones_digit_invalid: "その他支払いの1の位が不正です（10円単位ではありません）",
};

export function formatOcrValidationMessage(code: string): string {
  return OCR_VALIDATION_MESSAGE_JA[code] ?? code;
}

export function formatOcrValidationMessages(codes: string[] | null | undefined): string {
  if (!codes?.length) {
    return "OK";
  }
  return codes.map(formatOcrValidationMessage).join(" / ");
}
