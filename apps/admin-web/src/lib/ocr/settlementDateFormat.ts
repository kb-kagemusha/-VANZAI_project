/** 精算レシートの日付表示（YYYY/MM/DD）。 */
export function formatSettlementRecordDate(value: string | null | undefined): string {
  if (!value) {
    return "ー";
  }
  const normalized = value.trim().replace(/-/g, "/");
  if (/^\d{4}\/\d{2}\/\d{2}$/.test(normalized)) {
    return normalized;
  }
  return value;
}
