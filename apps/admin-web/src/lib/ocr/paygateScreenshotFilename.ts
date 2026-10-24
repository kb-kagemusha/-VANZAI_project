export type PaygateScreenshotFilenameRow = {
  record_date?: string | null;
  transaction_no?: string | null;
};

function extensionFromFilename(filename: string): string {
  const match = filename.match(/(\.[^./\\]+)$/i);
  return match?.[1] ?? ".png";
}

function minTransactionNo(transactionNos: string[]): string | null {
  if (!transactionNos.length) {
    return null;
  }
  return transactionNos.reduce((min, current) =>
    current.localeCompare(min, undefined, { numeric: true }) < 0 ? current : min,
  );
}

function earliestDate(dates: string[]): string | null {
  const sorted = [...dates].filter(Boolean).sort();
  return sorted[0] ?? null;
}

export function buildPaygateScreenshotFilename(
  rows: PaygateScreenshotFilenameRow[],
  sourceFilename?: string | null,
): string {
  const ext = extensionFromFilename(sourceFilename || ".png");
  const datePart = earliestDate(rows.map((row) => row.record_date || "").filter(Boolean))?.replace(/-/g, "") || "unknown";
  const minTxn = minTransactionNo(rows.map((row) => row.transaction_no || "").filter(Boolean)) || "unknown";
  return `Paygate精算画面_${datePart}_${minTxn}～${ext}`;
}
