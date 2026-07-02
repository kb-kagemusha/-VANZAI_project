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

export function normalizeYenAmount(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  const numeric = Number(String(value).replace(/,/g, ""));
  if (!Number.isFinite(numeric)) {
    return null;
  }

  return Math.round(numeric);
}

export function formatCurrency(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  const normalized = normalizeYenAmount(value);
  if (normalized === null) {
    return "-";
  }

  return new Intl.NumberFormat("ja-JP", {
    style: "currency",
    currency: "JPY",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(normalized);
}

/** 編集フォーム用。小数点なしの整数文字列を返す。 */
export function formatYenAmountPlain(value: string | number | null | undefined): string {
  const normalized = normalizeYenAmount(value);
  if (normalized === null) {
    return "";
  }
  return String(normalized);
}

export function formatMaskedAccountNumber(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  if (value.length <= 4) {
    return "*".repeat(value.length);
  }

  return `${"*".repeat(value.length - 4)}${value.slice(-4)}`;
}

export function toMonthInput(periodKey: string): string {
  return `${periodKey.slice(0, 4)}-${periodKey.slice(4, 6)}`;
}

export function toPeriodKey(monthValue: string): string {
  return monthValue.replace("-", "");
}

export function currentMonthInput(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
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
  const hours = minutes / 60;
  return `${hours.toFixed(1)}時間`;
}

export function formatPeriodKey(value: string | null | undefined): string {
  if (!value || value.length !== 6) {
    return value || "-";
  }

  return `${value.slice(0, 4)}年${value.slice(4, 6)}月`;
}

const STATUS_LABELS: Record<string, string> = {
  active: "有効",
  available: "稼働OK（1日）",
  available_all_day: "稼働OK（1日）",
  available_after_15: "稼働OK（15時〜）",
  inactive: "無効",
  invalid: "無効",
  sent: "送信済み",
  tentative: "仮確定",
  confirmed: "確定",
  pending: "保留",
  link_issued: "リンク発行済み",
  canceled: "取消",
  preparing: "準備中",
  issued: "発行済み",
  corrected: "訂正済み",
  approved: "承認済み",
  paid: "支払済み",
  processing: "処理中",
  completed: "完了",
  partial_error: "一部エラー",
  failed: "失敗",
  closed: "締め済み",
  soft_closed: "仮締め済み",
  hard_closed: "本締め済み",
  rejected: "却下",
  unavailable: "稼働不可",
  consult_required: "稼働はできなくはないので事前相談して",
  undecided: "未登録",
};

const ROLE_LABELS: Record<string, string> = {
  admin: "管理者",
  ops: "運用",
  accounting: "経理",
  site_manager: "現場責任者",
  worker: "稼働者",
};

const PAYEE_TYPE_LABELS: Record<string, string> = {
  worker: "稼働者",
  supplier: "取引先",
  vanzai_staff: "VANZAI担当者",
};

const IMPORT_MODE_LABELS: Record<string, string> = {
  append: "追加",
  replace_scope: "洗い替え",
  upsert_by_external_key: "外部キー更新",
};

const IMPORT_SCOPE_TYPE_LABELS: Record<string, string> = {
  project_month: "案件×月",
  project_day: "案件×日",
  project_day_worker: "案件×日×稼働者",
};

const AUDIT_ACTION_LABELS: Record<string, string> = {
  import_batch_created: "取込バッチ作成",
  import_batch_completed: "取込バッチ完了",
  replace_scope_executed: "洗い替え実行",
  actual_superseded: "実績差替え",
  actual_invalidated: "実績無効化",
  worker_created: "稼働者作成",
  worker_updated: "稼働者更新",
  supplier_created: "下請け作成",
  supplier_updated: "下請け更新",
  client_created: "クライアント作成",
  project_created: "案件作成",
  site_created: "現場作成",
  project_updated: "案件更新",
  project_type_created: "案件種別作成",
  role_created: "役割作成",
  price_rule_created: "単価ルール作成",
  price_rule_updated: "単価ルール更新",
  price_sales_created: "売上単価作成",
  price_sales_updated: "売上単価更新",
  price_outsource_created: "外注単価作成",
  price_outsource_updated: "外注単価更新",
  shift_slot_created: "シフト枠作成",
  shift_slot_updated: "シフト枠更新",
  assignment_created: "アサイン作成",
  assignment_updated: "アサイン更新",
  assignment_canceled: "アサイン取消",
  assignment_status_changed: "アサイン状態変更",
  assignment_worker_response_updated: "予定確認応答更新",
  assignment_response_reminder_sent: "予定確認催促送信",
  assignment_response_reminder_failed: "予定確認催促失敗",
  assignment_response_escalation_sent: "管理者通知送信",
  assignment_response_escalation_failed: "管理者通知失敗",
  assignment_selection_set_saved: "選択セット保存",
  assignment_selection_set_deleted: "選択セット削除",
  price_rule_changed: "単価ルール変更",
  price_resolved: "単価解決",
  closing_soft_closed: "仮締め実行",
  closing_soft_released: "仮締め解除",
  closing_hard_closed: "本締め実行",
  closing_hard_released: "本締め解除",
  invoice_created: "請求書作成",
  invoice_issued: "請求書発行",
  invoice_corrected: "請求書訂正",
  invoice_reissued: "請求書再発行",
  payout_created: "支払明細作成",
  payout_approved: "支払承認",
  payout_paid: "支払実行",
  payout_corrected: "支払訂正",
  payout_delivery_sent: "支払明細送信",
  payout_delivery_failed: "支払明細送信失敗",
  attendance_checked_in: "出勤打刻",
  attendance_checked_out: "退勤打刻",
  availability_updated: "稼働可否更新",
  expense_submitted: "経費申請",
  expense_approved: "経費承認",
  expense_rejected: "経費却下",
  registration_link_created: "公開リンク作成",
  registration_link_reissued: "公開リンク再発行",
  registration_link_pin_lock_reset: "公開リンクロック解除",
  registration_request_submitted: "登録申請送信",
  registration_request_file_uploaded: "登録申請ファイルアップロード",
  registration_request_file_downloaded: "登録申請ファイルダウンロード",
  registration_request_approved: "登録申請承認",
  registration_request_rejected: "登録申請却下",
};

export const AUDIT_ACTION_OPTION_GROUPS = [
  {
    label: "取込・実績・アサイン",
    options: [
      { value: "import_batch_created", label: "取込バッチ作成" },
      { value: "import_batch_completed", label: "取込バッチ完了" },
      { value: "replace_scope_executed", label: "洗い替え実行" },
      { value: "actual_superseded", label: "実績差替え" },
      { value: "actual_invalidated", label: "実績無効化" },
      { value: "assignment_updated", label: "アサイン更新" },
      { value: "assignment_canceled", label: "アサイン取消" },
      { value: "assignment_status_changed", label: "アサイン状態変更" },
      { value: "assignment_worker_response_updated", label: "予定確認応答更新" },
      { value: "assignment_response_reminder_sent", label: "予定確認催促送信" },
      { value: "assignment_response_reminder_failed", label: "予定確認催促失敗" },
      { value: "assignment_response_escalation_sent", label: "管理者通知送信" },
      { value: "assignment_response_escalation_failed", label: "管理者通知失敗" },
      { value: "assignment_selection_set_saved", label: "選択セット保存" },
      { value: "assignment_selection_set_deleted", label: "選択セット削除" },
    ],
  },
  {
    label: "単価・締め",
    options: [
      { value: "price_rule_changed", label: "単価ルール変更" },
      { value: "price_resolved", label: "単価解決" },
      { value: "closing_soft_closed", label: "仮締め実行" },
      { value: "closing_soft_released", label: "仮締め解除" },
      { value: "closing_hard_closed", label: "本締め実行" },
      { value: "closing_hard_released", label: "本締め解除" },
    ],
  },
  {
    label: "請求・支払",
    options: [
      { value: "invoice_created", label: "請求書作成" },
      { value: "invoice_issued", label: "請求書発行" },
      { value: "invoice_corrected", label: "請求書訂正" },
      { value: "invoice_reissued", label: "請求書再発行" },
      { value: "payout_created", label: "支払明細作成" },
      { value: "payout_approved", label: "支払承認" },
      { value: "payout_paid", label: "支払実行" },
      { value: "payout_corrected", label: "支払訂正" },
      { value: "payout_delivery_sent", label: "支払明細送信" },
      { value: "payout_delivery_failed", label: "支払明細送信失敗" },
    ],
  },
] as Array<{
  label: string;
  options: Array<{
    value: string;
    label: string;
  }>;
}>;

export const AUDIT_ACTION_OPTIONS: ReadonlyArray<{ value: string; label: string }> = AUDIT_ACTION_OPTION_GROUPS.flatMap((group) => group.options);

const AUDIT_TARGET_TYPE_LABELS: Record<string, string> = {
  import_batch: "取込バッチ",
  import_batches: "取込バッチ",
  actual: "実績",
  actuals: "実績",
  assignment: "アサイン",
  assignments: "アサイン",
  assignment_selection_set: "選択セット",
  assignment_selection_sets: "選択セット",
  project: "案件",
  projects: "案件",
  shift_slot: "シフト枠",
  shift_slots: "シフト枠",
  invoice: "請求書",
  invoices: "請求書",
  payout: "支払明細",
  payouts: "支払明細",
  payout_delivery: "支払明細送信",
  payout_deliveries: "支払明細送信",
  closing: "締め",
  closings: "締め",
  expense: "経費",
  expenses: "経費",
  incentive: "インセンティブ",
  incentives: "インセンティブ",
  price_sales: "売上単価",
  price_outsource: "外注単価",
  price_rule: "単価ルール",
  price_rules: "単価ルール",
  user: "ユーザー",
  users: "ユーザー",
};

export const AUDIT_TARGET_TYPE_OPTION_GROUPS = [
  {
    label: "月次運用",
    options: [
      { value: "import_batch", label: "取込バッチ" },
      { value: "actual", label: "実績" },
      { value: "assignment", label: "アサイン" },
      { value: "project", label: "案件" },
      { value: "shift_slot", label: "シフト枠" },
      { value: "closing", label: "締め" },
    ],
  },
  {
    label: "請求・支払",
    options: [
      { value: "invoice", label: "請求書" },
      { value: "payout", label: "支払明細" },
      { value: "expense", label: "経費" },
      { value: "incentive", label: "インセンティブ" },
    ],
  },
  {
    label: "設定・管理",
    options: [
      { value: "price_sales", label: "売上単価" },
      { value: "price_outsource", label: "外注単価" },
      { value: "price_rule", label: "単価ルール" },
      { value: "user", label: "ユーザー" },
    ],
  },
] as Array<{
  label: string;
  options: Array<{
    value: string;
    label: string;
  }>;
}>;

export const AUDIT_TARGET_TYPE_OPTIONS: ReadonlyArray<{ value: string; label: string }> = AUDIT_TARGET_TYPE_OPTION_GROUPS.flatMap((group) => group.options);

const AUDIT_SUMMARY_KEY_LABELS: Record<string, string> = {
  project_id: "案件ID",
  worker_id: "稼働者ID",
  client_id: "取引先ID",
  invoice_id: "請求書ID",
  payout_id: "支払明細ID",
  assignment_id: "アサインID",
  actual_id: "実績ID",
  expense_id: "経費ID",
  import_batch_id: "取込バッチID",
  period_key: "対象月",
  release_count: "解除回数",
  approver_id: "承認者",
  reclose_deadline: "再締め期限",
  current_count: "現在解除回数",
  max_count: "解除上限",
  approved_by: "承認者",
  approved_at: "承認日時",
  paid_at: "支払日時",
  status: "状態",
  reason: "理由",
  recipient_email: "送信先",
  delivery_note: "送信理由メモ",
  internal_note: "内部メモ",
  error_message: "エラー",
  provider: "プロバイダ",
};

export function formatAuditDetailValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "string") {
    if (/^\d{4}-\d{2}-\d{2}T/.test(value)) {
      return formatDateTime(value);
    }
    if (/^\d{6}$/.test(value)) {
      return formatPeriodKey(value);
    }
    return value;
  }
  return String(value);
}

export function formatStatus(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return STATUS_LABELS[value] || value;
}

const OCR_PARSE_STATUS_LABELS: Record<string, string> = {
  pending: "解析待ち",
  completed: "完了",
  failed: "失敗",
};

export function formatOcrParseStatus(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return OCR_PARSE_STATUS_LABELS[value] || formatStatus(value);
}

export function formatRole(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return ROLE_LABELS[value] || value;
}

export function formatPayeeType(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return PAYEE_TYPE_LABELS[value] || value;
}

export function formatAuditAction(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return AUDIT_ACTION_LABELS[value] || value;
}

export function formatAuditTargetType(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  const normalizedValue = value.toLowerCase();
  return AUDIT_TARGET_TYPE_LABELS[normalizedValue] || value;
}

export function formatAuditSummary(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  return value.replace(/\b([a-z_]+)=/g, (match, key: string) => {
    const label = AUDIT_SUMMARY_KEY_LABELS[key];
    return label ? `${label}=` : match;
  });
}

export function formatImportMode(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  return IMPORT_MODE_LABELS[value] || value;
}

export function formatImportScopeType(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  return IMPORT_SCOPE_TYPE_LABELS[value] || value;
}