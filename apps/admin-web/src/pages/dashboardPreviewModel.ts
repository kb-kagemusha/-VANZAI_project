import type { DashboardClosingStatus, DashboardUnprocessedItem } from "../types/api";

export const PREVIEW_PATH = "/dashboard/preview";

export const NAV_GROUP_ORDER = ["概要", "運用", "請求・支払", "マスタ", "監査", "その他"] as const;

export type NavGroup = (typeof NAV_GROUP_ORDER)[number];

export function navGroupFor(path: string): NavGroup {
  if (path.startsWith("/dashboard")) {
    return "概要";
  }
  if (path.startsWith("/operations")) {
    return "運用";
  }
  if (path.startsWith("/billing")) {
    return "請求・支払";
  }
  if (path.startsWith("/masters")) {
    return "マスタ";
  }
  if (path.startsWith("/audit-logs")) {
    return "監査";
  }
  return "その他";
}

export function activeNavPath(pathname: string, paths: readonly string[]): string | null {
  const matches = paths.filter((path) => pathname === path || pathname.startsWith(`${path}/`));
  if (matches.length === 0) {
    return null;
  }
  return [...matches].sort((left, right) => right.length - left.length)[0];
}

export type ClosingBarState =
  | { kind: "empty" }
  | { kind: "mismatch" }
  | { kind: "ratio"; closed: number; total: number; percent: number };

export function closingBarState(rows: Pick<DashboardClosingStatus, "project_id" | "status">[]): ClosingBarState {
  if (rows.length === 0) {
    return { kind: "empty" };
  }
  const projectIds = new Set(rows.map((row) => row.project_id));
  if (projectIds.size !== rows.length) {
    return { kind: "mismatch" };
  }
  const closed = rows.filter((row) => row.status === "soft_closed" || row.status === "hard_closed").length;
  const total = rows.length;
  return {
    kind: "ratio",
    closed,
    total,
    percent: Math.round((closed / total) * 100),
  };
}

export function unprocessedCount(items: DashboardUnprocessedItem[], itemType: string): number {
  return items.find((item) => item.item_type === itemType)?.count ?? 0;
}

export const KPI_ITEMS = [
  { itemType: "escalated_assignment_response", label: "要対応" },
  { itemType: "unissued_invoice", label: "未発行請求" },
  { itemType: "unprocessed_payout", label: "未処理支払" },
  { itemType: "unclosed_projects", label: "未締め案件" },
  { itemType: "assignment_variance", label: "差異配置" },
  { itemType: "missing_price", label: "単価未設定" },
  { itemType: "missing_payout_recipient", label: "送信先未設定支払" },
  { itemType: "pending_assignment_response", label: "予定確認未回答" },
] as const;

export function previewStatusLabel(status: string, formatStatus: (value: string) => string): string {
  if (status === "open") {
    return "未締め";
  }
  return formatStatus(status);
}

export function previewStatusTone(status: string): "positive" | "warning" | "neutral" {
  if (status === "hard_closed") {
    return "positive";
  }
  if (status === "soft_closed") {
    return "warning";
  }
  return "neutral";
}
