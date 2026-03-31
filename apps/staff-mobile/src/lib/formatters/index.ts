export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}

export function formatCurrency(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  return new Intl.NumberFormat("ja-JP", {
    style: "currency",
    currency: "JPY",
    maximumFractionDigits: 0,
  }).format(Number(value));
}

export function formatStatus(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  const labels: Record<string, string> = {
    tentative: "仮確定",
    confirmed: "確定",
    canceled: "取消",
    accepted: "参加可",
    declined: "辞退",
    valid: "有効",
    invalid: "無効",
    pending: "申請中",
    approved: "承認済み",
    rejected: "却下",
    available: "対応可",
    unavailable: "不可",
    undecided: "未回答",
  };

  return labels[value] || value;
}

export function currentMonthInput(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export function toPeriodKey(monthValue: string): string {
  return monthValue.replace("-", "");
}

export function periodKeyToDateRange(periodKey: string): { from: string; to: string } {
  const year = Number(periodKey.slice(0, 4));
  const month = Number(periodKey.slice(4, 6));
  const lastDay = new Date(year, month, 0).getDate();

  return {
    from: `${periodKey.slice(0, 4)}-${periodKey.slice(4, 6)}-01`,
    to: `${periodKey.slice(0, 4)}-${periodKey.slice(4, 6)}-${String(lastDay).padStart(2, "0")}`,
  };
}

export function minutesToHours(minutes: number): string {
  return `${(minutes / 60).toFixed(1)}h`;
}

export function currentDateInput(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

export function formatTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  return value.slice(0, 5);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function addDays(value: string, days: number): string {
  const dateValue = new Date(value);
  dateValue.setDate(dateValue.getDate() + days);
  return dateValue.toISOString().slice(0, 10);
}