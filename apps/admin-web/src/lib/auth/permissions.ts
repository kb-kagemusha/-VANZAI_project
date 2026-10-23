import type { AuthUser, UserRole } from "../../types/api";

export interface NavItem {
  to: string;
  label: string;
  description: string;
  allowedRoles: UserRole[];
}

export const DASHBOARD_ROLES: UserRole[] = ["admin", "ops", "accounting", "site_manager"];

export const NAV_ITEMS: NavItem[] = [
  { to: "/billing/order-amounts", label: "依頼書の金額確定", description: "請求額の確定と依頼元別の月次請求書", allowedRoles: ["admin"] },
  { to: "/settings/access", label: "ID・権限管理", description: "ログインIDと役割ごとの権限を設定", allowedRoles: ["admin"] },
  {
    to: "/dashboard",
    label: "ダッシュボード",
    description: "月次の未処理と締め状況",
    allowedRoles: DASHBOARD_ROLES,
  },
  {
    to: "/dashboard/preview",
    label: "見た目プレビュー",
    description: "参考デザインとの比較用。締め操作は現行ダッシュボードで行う",
    allowedRoles: DASHBOARD_ROLES,
  },
  {
    to: "/operations/calendar",
    label: "カレンダー",
    description: "出勤可能日・イベントごと・稼働者ごと・参加カレンダーを切り替えて表示",
    allowedRoles: ["admin", "ops", "accounting", "site_manager"],
  },
  {
    to: "/operations/order-requests",
    label: "発注依頼書",
    description: "依頼書の確定、送付先、受領の共有",
    allowedRoles: ["admin", "ops"],
  },
  {
    to: "/operations/wake-status",
    label: "起床状況",
    description: "当日の稼働予定と公式LINEの起床報告",
    allowedRoles: ["admin", "ops"],
  },
  {
    to: "/operations/notices",
    label: "スタッフ通知",
    description: "シフト確定・案件変更などをスタッフへ通知",
    allowedRoles: ["admin", "ops"],
  },
  {
    to: "/operations/registration-requests",
    label: "登録申請",
    description: "公開リンク発行と申請承認を管理",
    allowedRoles: ["admin", "ops", "accounting"],
  },
  {
    to: "/operations/csv-import",
    label: "CSV取込",
    description: "実績CSVの提出と洗い替え",
    allowedRoles: ["admin", "ops", "site_manager"],
  },
  {
    to: "/operations/ocr",
    label: "レシートOCR",
    description: "Paygateスクリーンショットと精算レシートのOCR解析",
    allowedRoles: ["admin", "ops", "accounting"],
  },
  {
    to: "/operations/actuals",
    label: "実績一覧",
    description: "実績の確認と差戻し前提の確認",
    allowedRoles: ["admin", "ops", "accounting", "site_manager"],
  },
  {
    to: "/operations/assignments",
    label: "配置一覧",
    description: "予定と確定配置の参照",
    allowedRoles: ["admin", "ops", "accounting", "site_manager"],
  },
  {
    to: "/operations/assignment-responses",
    label: "予定確認監視",
    description: "未回答と要対応の監視",
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
    to: "/masters/workers",
    label: "稼働者登録・一覧",
    description: "稼働者（スタッフ）の登録、一覧、公式LINEの本人紐付け",
    allowedRoles: ["admin", "ops", "accounting", "site_manager"],
  },
  {
    to: "/masters/prices",
    label: "単価一覧",
    description: "売上・外注・ルール単価を参照",
    allowedRoles: ["admin", "ops", "accounting"],
  },
  {
    to: "/masters/operator-staff",
    label: "運営スタッフ登録・一覧",
    description: "運営スタッフの登録、連絡先、付与ロール、公式LINEの本人紐付け",
    allowedRoles: ["admin"],
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

export function hasPermission(user: AuthUser | null, permission: string): boolean {
  return !!user && user.is_active && (user.role === "admin" || !!user.permissions?.includes(permission));
}

export const PATH_PERMISSIONS: Record<string, string[]> = {
  "/dashboard": ["dashboard_read"], "/dashboard/preview": ["dashboard_read"],
  "/operations/projects": ["project_read"], "/operations/shift-slots": ["shift_read"],
  "/operations/actuals": ["actual_read"], "/operations/assignments": ["assignment_read"],
  "/operations/assignment-responses": ["assignment_read"],
  "/operations/availability-calendar": ["availability_read"],
  "/operations/csv-import": ["csv_import", "csv_submit"],
  "/operations/ocr": ["ocr_read"], "/operations/order-requests": ["order_read"],
  "/operations/wake-status": ["wake_status_read"],
  "/operations/participation-calendar": ["order_read"],
  "/operations/order-overview": ["order_read"],
  "/operations/calendar": ["availability_read", "order_read"],
  "/operations/notices": ["notice_read"], "/operations/registration-requests": ["registration_read"],
  "/billing/invoices": ["invoice_read"], "/billing/payouts": ["payout_read"], "/billing/expenses": ["expense_read"],
  "/masters/workers": ["master_read"], "/masters/data": ["master_read"],
  "/masters/prices": ["price_read"], "/audit-logs": ["audit_log_read"],
};

export function canView(user: AuthUser | null, path: string, fallbackRoles: UserRole[] = []): boolean {
  if (!user?.is_active) return false;
  if (user.role === "admin") return true;
  if (path === "/billing/order-amounts" || path.startsWith("/billing/order-amounts/")) return false;
  if (path.startsWith("/dashboard/preview")) return false;
  if (path.startsWith("/settings/") || path === "/operations/order-requests/deleted") return false;
  const key = Object.keys(PATH_PERMISSIONS).sort((a, b) => b.length - a.length).find(item => path === item || path.startsWith(item + "/"));
  return key ? PATH_PERMISSIONS[key].some(permission => hasPermission(user, permission)) : canAccess(user.role, fallbackRoles);
}
