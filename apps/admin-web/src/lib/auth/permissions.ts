import type { UserRole } from "../../types/api";

export interface NavItem {
  to: string;
  label: string;
  description: string;
  allowedRoles: UserRole[];
}

export const DASHBOARD_ROLES: UserRole[] = ["admin", "ops", "accounting", "site_manager"];

export const NAV_ITEMS: NavItem[] = [
  {
    to: "/dashboard",
    label: "ダッシュボード",
    description: "月次の未処理と締め状況",
    allowedRoles: DASHBOARD_ROLES,
  },
  {
    to: "/operations/csv-import",
    label: "CSV取込",
    description: "実績CSVの提出と洗い替え",
    allowedRoles: ["admin", "ops", "site_manager"],
  },
  {
    to: "/operations/actuals",
    label: "実績一覧",
    description: "実績の確認と差戻し前提の確認",
    allowedRoles: ["admin", "ops", "accounting", "site_manager"],
  },
  {
    to: "/operations/assignments",
    label: "アサイン一覧",
    description: "予定と確定アサインの参照",
    allowedRoles: ["admin", "ops", "accounting", "site_manager"],
  },
  {
    to: "/operations/projects",
    label: "案件一覧",
    description: "案件、取引先、現場、期間の参照",
    allowedRoles: ["admin", "ops", "accounting", "site_manager"],
  },
  {
    to: "/operations/shift-slots",
    label: "シフト枠一覧",
    description: "シフト枠と充足状況の参照",
    allowedRoles: ["admin", "ops", "accounting", "site_manager"],
  },
  {
    to: "/billing/invoices",
    label: "請求一覧",
    description: "請求書の版と発行状況を参照",
    allowedRoles: ["admin", "ops", "accounting"],
  },
  {
    to: "/billing/payouts",
    label: "支払一覧",
    description: "支払明細の承認と支払状況を参照",
    allowedRoles: ["admin", "ops", "accounting"],
  },
  {
    to: "/billing/expenses",
    label: "経費一覧",
    description: "経費申請と承認状況を参照",
    allowedRoles: ["admin", "ops", "accounting"],
  },
  {
    to: "/masters/prices",
    label: "単価一覧",
    description: "売上・外注・ルール単価を参照",
    allowedRoles: ["admin", "ops", "accounting"],
  },
  {
    to: "/masters/data",
    label: "マスタ一覧",
    description: "稼働者・下請け・クライアント等のマスタデータを参照",
    allowedRoles: ["admin", "ops", "accounting", "site_manager"],
  },
  {
    to: "/audit-logs",
    label: "監査ログ",
    description: "監査ログを条件検索で参照",
    allowedRoles: ["admin", "ops", "accounting"],
  },
];

export function canAccess(role: UserRole | null | undefined, allowedRoles: UserRole[]): boolean {
  return role ? allowedRoles.includes(role) : false;
}