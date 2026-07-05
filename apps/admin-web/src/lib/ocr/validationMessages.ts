/** OCR 検証コード・英語メッセージ → 日本語 */
const OCR_VALIDATION_MESSAGE_JA: Record<string, string> = {
  amount_breakdown_mismatch:
    "金額の内訳（現金・クレジット・PAYGATE POS等）が合計と一致しません",
  settlement_amount_missing: "合計金額が読み取れません",
  transaction_count_invalid: "通常取引数が不正です",
  missing_terminal_short_id: "端末識別番号が未入力または読み取れません（4桁）",
  amount_ones_digit_invalid: "合計金額の1の位が不正です（10円単位ではありません）",
  cash_sales_ones_digit_invalid: "現金売上の1の位が不正です（10円単位ではありません）",
  pos_sales_ones_digit_invalid: "PAYGATE POS売上の1の位が不正です（10円単位ではありません）",
  pos_sales_unit_invalid:
    "PAYGATE POS売上が不正です（¥980/¥1,480/¥2,980の組み合わせではありません）",
  cash_sales_unit_invalid:
    "現金売上が不正です（¥980/¥1,480/¥2,980の組み合わせではありません）",
  credit_sales_ones_digit_invalid: "クレジット売上の1の位が不正です（10円単位ではありません）",
  other_payment_ones_digit_invalid: "その他支払いの1の位が不正です（10円単位ではありません）",
  duplicate_receipt_candidate: "同じ内容のレシートが既にある可能性があります（重複候補）",
  unit_breakdown_invalid: "現金/POSの台数内訳が取引数と整合しません",

  "record_date is missing": "日付が読み取れません",
  "transaction_no digit count is invalid": "取引番号の桁数が不正です",
  "receipt_no digit count is invalid": "レシート番号の桁数が不正です",
  "amount is missing": "金額が読み取れません",
  "record_time is missing": "時刻が読み取れません",
  "record_time format is invalid (expected HH:MM:SS)": "時刻の形式が不正です（HH:MM:SS）",
  "settlement total amount is missing": "精算の合計金額が読み取れません",
  "subtotal and total do not match": "小計と合計が一致しません",
  "cash_sales and total do not match": "現金売上と合計が一致しません",
  "transaction_count is invalid": "通常取引数が不正です",

  confirm_required: "要確認の項目があります",
  validation_errors: "検証エラーがあります",
  blocking_errors: "確定を妨げるエラーがあります",
  missing_record_date: "日付が未入力です",
  missing_record_time: "時刻が未入力です",
  missing_amount: "金額が未入力です",
  missing_transaction_no: "取引番号が未入力です",
  missing_receipt_no: "レシート番号が未入力です",
  missing_transaction_count: "通常取引数が未入力です",
  voided: "無効化済みの行です",
  deleted: "削除済みの行です",
  already_confirmed: "確定済みの行です",
  invalid_terminal_short_id: "端末識別番号は4桁の16進（0-9a-f）で入力してください",
  terminal_id_partial: "端末番号が一部のみ読み取れています。再解析または手入力で完全な値にしてください",
};

const OCR_IMAGE_ERROR_JA: Record<string, string> = {
  "No structured rows extracted": "レシートから有効なデータを抽出できませんでした",
  "Empty file": "空のファイルです",
  "File too large": "ファイルサイズが上限を超えています",
  "Image not found": "画像が見つかりません",
  "image_ids is required": "解析対象の画像が指定されていません",
  "Confirmed rows cannot be reparsed": "確定済みの行は再解析できません",
  "Only settlement rows support reparse": "精算レシート以外は再解析できません",
  "Row not found": "保存データが見つかりません",
  "Reparse target row is not available": "再解析対象の行が利用できません",
  "Filename is required": "ファイル名が必要です",
  "void_reason is required": "無効化には理由の入力が必須です",
  "excluded_reason is required when eligible=False": "在庫照合対象から除外するには理由の入力が必須です",
  "terminal_short_id must be exactly 4 hexadecimal characters":
    "端末識別番号は4桁の16進（0-9a-f）で入力してください",
};

const OCR_IMAGE_ERROR_PREFIX_JA: Array<[prefix: string, message: string]> = [
  ["Unsupported source_type:", "非対応の画像種別です"],
  ["reconciliation_eligible is only applicable", "在庫照合対象の設定は精算レシートのみ可能です"],
];

const UNIT_BREAKDOWN_STATUS_JA: Record<string, string> = {
  resolved: "確定",
  ambiguous: "複数候補あり",
  invalid: "整合不可",
  manual: "手動確認",
};

function translateKnownMessage(
  message: string,
  dictionary: Record<string, string>,
  prefixRules: Array<[string, string]>,
): string {
  const trimmed = message.trim();
  if (!trimmed) {
    return "";
  }
  if (dictionary[trimmed]) {
    return dictionary[trimmed];
  }
  for (const [prefix, translated] of prefixRules) {
    if (trimmed.startsWith(prefix)) {
      return translated;
    }
  }
  return trimmed;
}

export function formatOcrValidationMessage(code: string): string {
  return translateKnownMessage(code, OCR_VALIDATION_MESSAGE_JA, OCR_IMAGE_ERROR_PREFIX_JA);
}

export function formatOcrValidationMessages(codes: string[] | null | undefined): string {
  if (!codes?.length) {
    return "OK";
  }
  return codes.map(formatOcrValidationMessage).join(" / ");
}

export function formatOcrImageErrorMessage(message: string | null | undefined): string {
  if (!message) {
    return "";
  }
  const fromImage = translateKnownMessage(message, OCR_IMAGE_ERROR_JA, OCR_IMAGE_ERROR_PREFIX_JA);
  if (fromImage !== message.trim()) {
    return fromImage;
  }
  return formatOcrValidationMessage(message);
}

export function formatUnitBreakdownStatus(status: string | null | undefined): string {
  if (!status) {
    return "-";
  }
  return UNIT_BREAKDOWN_STATUS_JA[status] ?? status;
}
