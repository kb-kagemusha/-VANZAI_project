import { Navigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { PaginationBar } from "../components/PaginationBar";
import { getActuals, getAssignments, getExpenses, getImportBatches, getInvoices, getPayouts, getPriceOutsource, getPriceRules, getPriceSales, getProjects, getShiftSlots, searchAuditLogs, ApiError } from "../lib/api/client";
import { AUDIT_ACTION_OPTION_GROUPS, AUDIT_TARGET_TYPE_OPTION_GROUPS, currentMonthInput, formatAuditAction, formatAuditDetailValue, formatAuditSummary, formatAuditTargetType, formatCurrency, formatDateTime, formatPeriodKey, periodKeyToDateRange, toPeriodKey } from "../lib/formatters";

const PAGE_SIZE = 20;
const QUICK_FILTER_CONFIG = {
  all: { actionGroup: "", targetType: "", label: "すべて", description: "対象月の監査ログ全体を確認します。", targetHint: "案件や対象種別は個別条件で追加できます。" },
  import_all: { actionGroup: "import_all", targetType: "import_batch", label: "取込関連", description: "取込開始、完了、洗い替えの実行をまとめて確認します。", targetHint: "主に取込バッチが対象です。" },
  actual_all: { actionGroup: "actual_all", targetType: "actual", label: "実績関連", description: "実績の差替えや無効化を確認します。", targetHint: "実績レコードが対象です。" },
  assignment_all: { actionGroup: "assignment_all", targetType: "assignment", label: "アサイン関連", description: "アサインの取消や状態変更を確認します。", targetHint: "アサインが対象です。" },
  price_all: { actionGroup: "price_all", targetType: "", label: "単価関連", description: "単価ルール変更と単価解決をまとめて確認します。", targetHint: "単価ルール、売上単価、外注単価、アサインを含みます。" },
  closing_all: { actionGroup: "closing_all", targetType: "closing", label: "締め関連", description: "締め実行と締め解除をまとめて確認します。", targetHint: "締めレコードが対象です。" },
  closing_execute: { actionGroup: "closing_execute", targetType: "closing", label: "締め実行のみ", description: "仮締めと本締めの実行だけを確認します。", targetHint: "締め実行ログのみ表示します。" },
  closing_release: { actionGroup: "closing_release", targetType: "closing", label: "締め解除のみ", description: "仮締め解除と本締め解除だけを確認します。", targetHint: "解除理由や承認者の追跡に向いています。" },
  invoice_all: { actionGroup: "invoice_all", targetType: "invoice", label: "請求関連", description: "請求書の生成、発行、訂正、再発行を確認します。", targetHint: "請求書が対象です。" },
  payout_all: { actionGroup: "payout_all", targetType: "payout", label: "支払関連", description: "支払明細の生成、承認、支払、訂正を確認します。", targetHint: "支払明細が対象です。" },
} as const;

const QUICK_FILTER_BUTTON_KEYS: QuickFilterKey[] = [
  "all",
  "import_all",
  "actual_all",
  "assignment_all",
  "price_all",
  "closing_all",
  "closing_execute",
  "closing_release",
  "invoice_all",
  "payout_all",
];

type QuickFilterKey = keyof typeof QUICK_FILTER_CONFIG;

function periodKeyToMonthInput(periodKey: string | null): string {
  if (periodKey && /^\d{6}$/.test(periodKey)) {
    return `${periodKey.slice(0, 4)}-${periodKey.slice(4, 6)}`;
  }

  return currentMonthInput();
}

function parsePageParam(value: string | null): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 0;
}

function getQuickFilterFromSearchParams(searchParams: URLSearchParams): QuickFilterKey {
  const quickFilter = searchParams.get("quick_filter");
  if (quickFilter && quickFilter in QUICK_FILTER_CONFIG) {
    return quickFilter as QuickFilterKey;
  }

  return "all";
}

function resolveQuickFilterKey(actionGroup: string, targetType: string): QuickFilterKey | null {
  const entry = Object.entries(QUICK_FILTER_CONFIG).find(([, value]) => value.actionGroup === actionGroup && value.targetType === targetType);
  return entry ? (entry[0] as QuickFilterKey) : null;
}

export function AuditLogsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuickFilter = getQuickFilterFromSearchParams(searchParams);
  const initialQuickFilterConfig = QUICK_FILTER_CONFIG[initialQuickFilter];
  const [monthValue, setMonthValue] = useState(() => periodKeyToMonthInput(searchParams.get("period_key")));
  const [projectId, setProjectId] = useState(() => searchParams.get("project_id") || "");
  const [actionType, setActionType] = useState(() => searchParams.get("action_type") || "");
  const [actionGroup, setActionGroup] = useState(() => searchParams.get("action_group") || initialQuickFilterConfig.actionGroup);
  const [targetType, setTargetType] = useState(() => searchParams.get("target_type") || initialQuickFilterConfig.targetType);
  const [actor, setActor] = useState(() => searchParams.get("actor") || "");
  const [dateFrom, setDateFrom] = useState(() => searchParams.get("date_from") || "");
  const [dateTo, setDateTo] = useState(() => searchParams.get("date_to") || "");
  const [page, setPage] = useState(() => parsePageParam(searchParams.get("page")));
  const periodKey = toPeriodKey(monthValue);
  const { from: periodDateFrom, to: periodDateTo } = periodKeyToDateRange(periodKey);
  const activeQuickFilterKey = resolveQuickFilterKey(actionGroup, targetType) || "all";
  const activeQuickFilterLabel = QUICK_FILTER_CONFIG[activeQuickFilterKey].label;
  const quickFilterTargetType = QUICK_FILTER_CONFIG[activeQuickFilterKey].targetType;

  const clearFilters = () => {
    setProjectId("");
    setActionType("");
    setActionGroup(QUICK_FILTER_CONFIG.all.actionGroup);
    setTargetType(QUICK_FILTER_CONFIG.all.targetType);
    setActor("");
    setDateFrom("");
    setDateTo("");
    setPage(0);
  };

  const clearQuickFilter = () => {
    setActionGroup(QUICK_FILTER_CONFIG.all.actionGroup);
    setTargetType(QUICK_FILTER_CONFIG.all.targetType);
    setPage(0);
  };

  useEffect(() => {
    const nextMonthValue = periodKeyToMonthInput(searchParams.get("period_key"));
    const nextQuickFilter = getQuickFilterFromSearchParams(searchParams);
    const nextQuickFilterConfig = QUICK_FILTER_CONFIG[nextQuickFilter];
    const nextProjectId = searchParams.get("project_id") || "";
    const nextActionType = searchParams.get("action_type") || "";
    const nextActionGroup = searchParams.get("action_group") || nextQuickFilterConfig.actionGroup;
    const nextTargetType = searchParams.get("target_type") || nextQuickFilterConfig.targetType;
    const nextActor = searchParams.get("actor") || "";
    const nextDateFrom = searchParams.get("date_from") || "";
    const nextDateTo = searchParams.get("date_to") || "";
    const nextPage = parsePageParam(searchParams.get("page"));

    setMonthValue((current) => (current === nextMonthValue ? current : nextMonthValue));
    setProjectId((current) => (current === nextProjectId ? current : nextProjectId));
    setActionType((current) => (current === nextActionType ? current : nextActionType));
    setActionGroup((current) => (current === nextActionGroup ? current : nextActionGroup));
    setTargetType((current) => (current === nextTargetType ? current : nextTargetType));
    setActor((current) => (current === nextActor ? current : nextActor));
    setDateFrom((current) => (current === nextDateFrom ? current : nextDateFrom));
    setDateTo((current) => (current === nextDateTo ? current : nextDateTo));
    setPage((current) => (current === nextPage ? current : nextPage));
  }, [searchParams]);

  useEffect(() => {
    const nextParams = new URLSearchParams();
    nextParams.set("period_key", periodKey);
    nextParams.set("quick_filter", activeQuickFilterKey);
    if (projectId) {
      nextParams.set("project_id", projectId);
    }
    if (actionType) {
      nextParams.set("action_type", actionType);
    }
    if (actionGroup) {
      nextParams.set("action_group", actionGroup);
    }
    if (targetType) {
      nextParams.set("target_type", targetType);
    }
    if (actor) {
      nextParams.set("actor", actor);
    }
    if (dateFrom) {
      nextParams.set("date_from", dateFrom);
    }
    if (dateTo) {
      nextParams.set("date_to", dateTo);
    }
    if (page > 0) {
      nextParams.set("page", String(page));
    }

    if (nextParams.toString() !== searchParams.toString()) {
      setSearchParams(nextParams, { replace: true });
    }
  }, [periodKey, projectId, actionType, actionGroup, targetType, actor, dateFrom, dateTo, page, searchParams, setSearchParams]);

  const projectsQuery = useQuery({
    queryKey: ["projects-all-audit"],
    queryFn: () => getProjects({ limit: 200, is_active: true, sort_by: "name", sort_order: "asc" }),
  });
  const invoiceTargetsQuery = useQuery({
    queryKey: ["audit-invoice-targets", periodKey],
    queryFn: () =>
      getInvoices({
        period_key: periodKey,
        sort_by: "issued_at",
        sort_order: "desc",
        offset: 0,
        limit: 200,
      }),
    select: (data) => new Map(data.items.map((invoice) => [invoice.id, `${invoice.invoice_number}${invoice.project_name ? ` / ${invoice.project_name}` : ""}`])),
  });
  const payoutTargetsQuery = useQuery({
    queryKey: ["audit-payout-targets", periodKey],
    queryFn: () =>
      getPayouts({
        period_key: periodKey,
        sort_by: "approved_at",
        sort_order: "desc",
        offset: 0,
        limit: 200,
      }),
    select: (data) => new Map(data.items.map((payout) => [payout.id, `${payout.payout_number}${payout.payee_name ? ` / ${payout.payee_name}` : ""}`])),
  });
  const importBatchTargetsQuery = useQuery({
    queryKey: ["audit-import-batch-targets", periodKey],
    queryFn: () =>
      getImportBatches({
        period_key: periodKey,
        offset: 0,
        limit: 200,
      }),
    select: (data) => new Map(data.items.map((batch) => [batch.id, `${batch.file_name}${batch.project_name ? ` / ${batch.project_name}` : ""}`])),
  });
  const actualTargetsQuery = useQuery({
    queryKey: ["audit-actual-targets", periodKey],
    queryFn: () =>
      getActuals({
        period_key: periodKey,
        offset: 0,
        limit: 200,
      }),
    select: (data) =>
      new Map(
        data.items.map((actual) => [
          actual.id,
          `${actual.worker_name}${actual.project_name ? ` / ${actual.project_name}` : ""}${actual.work_date ? ` / ${actual.work_date}` : ""}`,
        ]),
      ),
  });
  const shiftSlotsWorkDateFrom = periodDateFrom;
  const shiftSlotsWorkDateTo = periodDateTo;
  const shiftSlotTargetsQuery = useQuery({
    queryKey: ["audit-shift-slot-targets", periodKey],
    queryFn: () =>
      getShiftSlots({
        work_date_from: shiftSlotsWorkDateFrom,
        work_date_to: shiftSlotsWorkDateTo,
        offset: 0,
        limit: 200,
      }),
    select: (data) =>
      new Map(
        data.items.map((slot) => [
          slot.id,
          `${slot.project_name}${slot.work_date ? ` / ${slot.work_date}` : ""}${slot.shift_label ? ` / ${slot.shift_label}` : ""}`,
        ]),
      ),
  });
  const expensesDateFrom = periodDateFrom;
  const expensesDateTo = periodDateTo;
  const expenseTargetsQuery = useQuery({
    queryKey: ["audit-expense-targets", periodKey],
    queryFn: () =>
      getExpenses({
        expense_date_from: expensesDateFrom,
        expense_date_to: expensesDateTo,
        offset: 0,
        limit: 200,
      }),
    select: (data) =>
      new Map(
        data.items.map((expense) => [
          expense.id,
          `${expense.category}${expense.project_name ? ` / ${expense.project_name}` : ""}${expense.worker_name ? ` / ${expense.worker_name}` : ""}`,
        ]),
      ),
  });
  const priceRuleTargetsQuery = useQuery({
    queryKey: ["audit-price-rule-targets"],
    queryFn: () =>
      getPriceRules({
        offset: 0,
        limit: 200,
        sort_by: "priority",
        sort_order: "asc",
      }),
    select: (data) => new Map(data.items.map((rule) => [rule.id, rule.name])),
  });
  const priceSalesTargetsQuery = useQuery({
    queryKey: ["audit-price-sales-targets"],
    queryFn: () =>
      getPriceSales({
        offset: 0,
        limit: 200,
      }),
    select: (data) =>
      new Map(
        data.items.map((price) => [
          price.id,
          `${price.project_name || price.client_name || "売上単価"}${price.role_name ? ` / ${price.role_name}` : ""}${price.is_default ? " / 既定" : ""}`,
        ]),
      ),
  });
  const priceOutsourceTargetsQuery = useQuery({
    queryKey: ["audit-price-outsource-targets"],
    queryFn: () =>
      getPriceOutsource({
        offset: 0,
        limit: 200,
      }),
    select: (data) =>
      new Map(
        data.items.map((price) => [
          price.id,
          `${price.project_name || price.worker_name || "外注単価"}${price.worker_name && !price.project_name ? ` / ${price.worker_name}` : ""}${price.role_name ? ` / ${price.role_name}` : ""}${price.is_default ? " / 既定" : ""}`,
        ]),
      ),
  });
  const assignmentsWorkDateFrom = periodDateFrom;
  const assignmentsWorkDateTo = periodDateTo;
  const assignmentTargetsQuery = useQuery({
    queryKey: ["audit-assignment-targets", periodKey],
    queryFn: () =>
      getAssignments({
        work_date_from: assignmentsWorkDateFrom,
        work_date_to: assignmentsWorkDateTo,
        offset: 0,
        limit: 200,
      }),
    select: (data) =>
      new Map(
        data.items.map((assignment) => [
          assignment.id,
          `${assignment.worker_name}${assignment.project_name ? ` / ${assignment.project_name}` : ""}${assignment.work_date ? ` / ${assignment.work_date}` : ""}`,
        ]),
      ),
  });
  const projectNameMap = new Map((projectsQuery.data?.items ?? []).map((project) => [project.id, project.name]));
  const getProjectLabel = (candidateProjectId: string | null | undefined) => {
    if (!candidateProjectId) {
      return "-";
    }

    return projectNameMap.get(candidateProjectId) || candidateProjectId;
  };
  const activeQuickFilterDescription = QUICK_FILTER_CONFIG[activeQuickFilterKey].description;
  const activeQuickFilterTargetHint = QUICK_FILTER_CONFIG[activeQuickFilterKey].targetHint;
  const formatPriceResolutionMethod = (method: string | null, priceType: string | null) => {
    const methodLabelMap: Record<string, string> = {
      locked_price_sales: "アサイン固定単価",
      locked_price_outsource: "アサイン固定単価",
      project_price: "案件単価",
      price_rule: "単価ルール一致",
      default: "既定単価",
      not_found: "単価未解決",
    };
    const priceTypeLabel = priceType === "outsource" ? "外注単価" : "売上単価";
    return `${priceTypeLabel} / ${method ? (methodLabelMap[method] || method) : "解決"}`;
  };
  const getTargetDisplay = (row: {
    target_type: string | null;
    target_id: string | null;
    project_id: string | null;
    details: Record<string, unknown> | null;
  }) => {
    if (!row.target_id) {
      return "-";
    }

    const normalizedTargetType = row.target_type?.toLowerCase() || "";
    if (normalizedTargetType === "project" || normalizedTargetType === "projects") {
      return getProjectLabel(row.target_id);
    }

    if (normalizedTargetType === "closing" || normalizedTargetType === "closings") {
      const periodKey = typeof row.details?.period_key === "string" ? row.details.period_key : null;
      if (row.project_id && periodKey) {
        return `${getProjectLabel(row.project_id)} / ${formatPeriodKey(periodKey)}`;
      }
      if (row.project_id) {
        return getProjectLabel(row.project_id);
      }
      if (periodKey) {
        return formatPeriodKey(periodKey);
      }
    }

    if (normalizedTargetType === "invoice" || normalizedTargetType === "invoices") {
      return invoiceTargetsQuery.data?.get(row.target_id) || row.target_id;
    }

    if (normalizedTargetType === "payout" || normalizedTargetType === "payouts") {
      return payoutTargetsQuery.data?.get(row.target_id) || row.target_id;
    }

    if (normalizedTargetType === "import_batch" || normalizedTargetType === "import_batches") {
      return importBatchTargetsQuery.data?.get(row.target_id) || row.target_id;
    }

    if (normalizedTargetType === "shift_slot" || normalizedTargetType === "shift_slots") {
      return shiftSlotTargetsQuery.data?.get(row.target_id) || row.target_id;
    }

    if (normalizedTargetType === "expense" || normalizedTargetType === "expenses") {
      return expenseTargetsQuery.data?.get(row.target_id) || row.target_id;
    }

    if (normalizedTargetType === "actual" || normalizedTargetType === "actuals") {
      return actualTargetsQuery.data?.get(row.target_id) || row.target_id;
    }

    if (normalizedTargetType === "assignment" || normalizedTargetType === "assignments") {
      return assignmentTargetsQuery.data?.get(row.target_id) || row.target_id;
    }

    if (normalizedTargetType === "price_rule" || normalizedTargetType === "price_rules") {
      const ruleLabel = priceRuleTargetsQuery.data?.get(row.target_id);
      if (ruleLabel) {
        return ruleLabel;
      }

      const ruleName =
        (typeof row.details?.rule_name === "string" && row.details.rule_name) ||
        (typeof row.details?.name === "string" && row.details.name) ||
        null;
      if (ruleName) {
        return ruleName;
      }

      return `単価ルール ${row.target_id}`;
    }

    if (normalizedTargetType === "price_sales") {
      return priceSalesTargetsQuery.data?.get(row.target_id) || `売上単価 ${row.target_id}`;
    }

    if (normalizedTargetType === "price_outsource") {
      return priceOutsourceTargetsQuery.data?.get(row.target_id) || `外注単価 ${row.target_id}`;
    }

    return row.target_id;
  };
  const getSummaryDisplay = (row: {
    action: string;
    project_id: string | null;
    target_type: string | null;
    target_id: string | null;
    reason: string | null;
    details: Record<string, unknown> | null;
    details_summary: string | null;
  }) => {
    const details = row.details || {};

    if (row.action === "price_resolved") {
      const method = typeof details.method === "string" ? details.method : null;
      const priceType = typeof details.price_type === "string" ? details.price_type : null;
      const targetDate = typeof details.target_date === "string" ? details.target_date : null;
      const price = details.price;
      return [
        formatPriceResolutionMethod(method, priceType),
        typeof price === "number" || typeof price === "string" ? formatCurrency(price) : null,
        targetDate ? formatAuditDetailValue(targetDate) : null,
      ].filter((value): value is string => Boolean(value)).join(" / ");
    }

    if (row.action === "closing_soft_closed" || row.action === "closing_hard_closed") {
      const period = typeof details.period_key === "string" ? formatPeriodKey(details.period_key) : null;
      return [getProjectLabel(row.project_id), period, "締め実行"].filter((value): value is string => Boolean(value) && value !== "-").join(" / ");
    }

    if (row.action === "closing_soft_released" || row.action === "closing_hard_released") {
      return [
        typeof details.reason === "string" ? `解除理由: ${details.reason}` : null,
        typeof details.approver_id === "string" ? `承認者: ${details.approver_id}` : null,
        typeof details.reclose_deadline === "string" ? `再締め期限: ${formatAuditDetailValue(details.reclose_deadline)}` : null,
      ].filter((value): value is string => Boolean(value)).join(" / ");
    }

    if (row.action === "import_batch_completed") {
      return [
        typeof details.count_success === "number" ? `成功 ${details.count_success}件` : null,
        typeof details.count_error === "number" ? `エラー ${details.count_error}件` : null,
        typeof details.count_superseded === "number" ? `洗替え ${details.count_superseded}件` : null,
      ].filter((value): value is string => Boolean(value)).join(" / ");
    }

    if (row.action === "replace_scope_executed") {
      return [
        typeof details.scope_type === "string" ? `範囲: ${details.scope_type}` : null,
        typeof details.superseded_count === "number" ? `無効化 ${details.superseded_count}件` : null,
      ].filter((value): value is string => Boolean(value)).join(" / ");
    }

    if (row.action === "actual_invalidated" && row.reason) {
      return `無効化理由: ${row.reason}`;
    }

    if (row.action === "assignment_canceled" && row.reason) {
      return `取消理由: ${row.reason}`;
    }

    if (row.action === "payout_delivery_sent" || row.action === "payout_delivery_failed") {
      return [
        typeof details.recipient_email === "string" ? `送信先: ${details.recipient_email}` : null,
        typeof details.delivery_note === "string" && details.delivery_note ? `送信理由: ${details.delivery_note}` : null,
        typeof details.internal_note === "string" && details.internal_note ? `内部メモ: ${details.internal_note}` : null,
        typeof details.provider === "string" ? `プロバイダ: ${details.provider}` : null,
        typeof details.error_message === "string" && details.error_message ? `エラー: ${details.error_message}` : null,
      ].filter((value): value is string => Boolean(value)).join(" / ") || formatAuditSummary(row.details_summary || row.reason);
    }

    return formatAuditSummary(row.details_summary || row.reason);
  };
  const selectedProjectName = getProjectLabel(projectId);
  const pageDescription = projectId
    ? `案件 ${selectedProjectName} を中心に、対象月、操作種別、実行者、日付範囲で監査ログを検索します。`
    : "対象月、操作種別、実行者、日付範囲で監査ログを検索します。";
  const manualFilterLabels = [
    projectId ? `案件=${selectedProjectName}` : null,
    actionType ? `操作=${formatAuditAction(actionType)}` : null,
    targetType && targetType !== quickFilterTargetType ? `対象=${formatAuditTargetType(targetType)}` : null,
    actor ? `実行者=${actor}` : null,
    dateFrom ? `開始=${dateFrom}` : null,
    dateTo ? `終了=${dateTo}` : null,
  ].filter((value): value is string => Boolean(value));
  const filterChips: Array<{ key: string; label: string; onClear: () => void }> = [
    ...(activeQuickFilterKey !== "all"
      ? [{ key: "quick_filter", label: `クイック: ${activeQuickFilterLabel}`, onClear: clearQuickFilter }]
      : []),
    ...(projectId ? [{ key: "project_id", label: `案件: ${selectedProjectName}`, onClear: () => { setProjectId(""); setPage(0); } }] : []),
    ...(actionType ? [{ key: "action_type", label: `操作: ${formatAuditAction(actionType)}`, onClear: () => { setActionType(""); setPage(0); } }] : []),
    ...(targetType && targetType !== quickFilterTargetType ? [{ key: "target_type", label: `対象: ${formatAuditTargetType(targetType)}`, onClear: () => { setTargetType(""); setPage(0); } }] : []),
    ...(actor ? [{ key: "actor", label: `実行者: ${actor}`, onClear: () => { setActor(""); setPage(0); } }] : []),
    ...(dateFrom ? [{ key: "date_from", label: `開始: ${dateFrom}`, onClear: () => { setDateFrom(""); setPage(0); } }] : []),
    ...(dateTo ? [{ key: "date_to", label: `終了: ${dateTo}`, onClear: () => { setDateTo(""); setPage(0); } }] : []),
  ];

  const auditLogsQuery = useQuery({
    queryKey: ["audit-logs", periodKey, projectId, actionType, actionGroup, targetType, actor, dateFrom, dateTo, page],
    queryFn: () =>
      searchAuditLogs({
        period_key: periodKey,
        project_id: projectId || undefined,
        action_type: actionType || undefined,
        action_group: actionGroup || undefined,
        target_type: targetType || undefined,
        actor: actor || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
  });

  if (auditLogsQuery.isLoading) {
    return <LoadingOverlay label="監査ログを読み込み中..." />;
  }

  if (auditLogsQuery.error instanceof ApiError && auditLogsQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (auditLogsQuery.isError || !auditLogsQuery.data) {
    return <ErrorState title="監査ログの取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  return (
    <div className="page-stack">
      <PageHeader title="監査ログ" description={pageDescription} />
      <section className="upload-card">
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
          <strong>クイックフィルタ</strong>
          {QUICK_FILTER_BUTTON_KEYS.map((filterKey) => {
            const filterConfig = QUICK_FILTER_CONFIG[filterKey];
            return (
              <button
                key={filterKey}
                type="button"
                onClick={() => {
                  setActionGroup(filterConfig.actionGroup);
                  setTargetType(filterConfig.targetType);
                  setPage(0);
                }}
                style={{ opacity: activeQuickFilterKey === filterKey ? 1 : 0.7 }}
              >
                {filterConfig.label}
              </button>
            );
          })}
          <button type="button" onClick={clearFilters}>
            条件をクリア
          </button>
        </div>
        <p style={{ margin: "0.5rem 0 0", color: "var(--color-muted)" }}>
          選択中: {activeQuickFilterLabel}
          {manualFilterLabels.length > 0 ? ` / 個別条件: ${manualFilterLabels.join(" / ")}` : ""}
        </p>
        <p style={{ margin: "0.35rem 0 0", color: "var(--color-muted)" }}>
          {activeQuickFilterDescription} {activeQuickFilterTargetHint}
        </p>
        {filterChips.length > 0 ? (
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.75rem" }}>
            {filterChips.map((chip) => (
              <button
                key={chip.key}
                type="button"
                onClick={chip.onClear}
                style={{
                  border: "1px solid var(--color-border, #d0d5dd)",
                  borderRadius: "999px",
                  background: "var(--color-surface, #fff)",
                  padding: "0.35rem 0.65rem",
                }}
              >
                {chip.label} ×
              </button>
            ))}
          </div>
        ) : null}
      </section>
      <FilterBar>
        <label>
          対象月
          <input type="month" value={monthValue} onChange={(event) => { setMonthValue(event.target.value); setPage(0); }} />
        </label>
        <label>
          案件
          <select value={projectId} onChange={(event) => { setProjectId(event.target.value); setPage(0); }}>
            <option value="">すべての案件</option>
            {(projectsQuery.data?.items ?? []).map((project) => (
              <option key={project.id} value={project.id}>{project.name}</option>
            ))}
          </select>
        </label>
        <label>
          操作種別
          <select value={actionType} onChange={(event) => { setActionType(event.target.value); setPage(0); }}>
            <option value="">すべての操作</option>
            {AUDIT_ACTION_OPTION_GROUPS.map((group) => (
              <optgroup key={group.label} label={group.label}>
                {group.options.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        <label>
          対象種別
          <select value={targetType} onChange={(event) => { setTargetType(event.target.value); setPage(0); }}>
            <option value="">すべての対象</option>
            {AUDIT_TARGET_TYPE_OPTION_GROUPS.map((group) => (
              <optgroup key={group.label} label={group.label}>
                {group.options.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        <label>
          実行者
          <input value={actor} onChange={(event) => { setActor(event.target.value); setPage(0); }} placeholder="例: 運用担当者ID" />
        </label>
        <label>
          開始日
          <input type="date" value={dateFrom} onChange={(event) => { setDateFrom(event.target.value); setPage(0); }} />
        </label>
        <label>
          終了日
          <input type="date" value={dateTo} onChange={(event) => { setDateTo(event.target.value); setPage(0); }} />
        </label>
      </FilterBar>

      <DataTable
        columns={[
          { key: "timestamp", header: "日時", render: (row) => formatDateTime(row.timestamp) },
          { key: "action", header: "操作", render: (row) => formatAuditAction(row.action) },
          { key: "actor", header: "実行者", render: (row) => row.actor || "-" },
          { key: "project", header: "案件", render: (row) => getProjectLabel(row.project_id) },
          { key: "targetType", header: "対象種別", render: (row) => formatAuditTargetType(row.target_type) },
          { key: "targetId", header: "対象", render: (row) => getTargetDisplay(row) },
          { key: "approver", header: "承認者", render: (row) => formatAuditDetailValue(row.details?.approver_id) },
          { key: "deadline", header: "再締め期限", render: (row) => formatAuditDetailValue(row.details?.reclose_deadline) },
          { key: "reason", header: "理由", render: (row) => formatAuditDetailValue(row.reason || row.details?.reason) },
          { key: "summary", header: "概要", render: (row) => getSummaryDisplay(row) },
        ]}
        rows={auditLogsQuery.data.items}
        getRowKey={(row) => row.id}
        emptyTitle="監査ログはありません"
        emptyDescription="条件に一致する監査ログは見つかりませんでした。"
      />

      <PaginationBar
        page={page}
        total={auditLogsQuery.data.total}
        limit={auditLogsQuery.data.limit}
        onPrevious={() => setPage((value) => Math.max(0, value - 1))}
        onNext={() => setPage((value) => value + 1)}
      />
    </div>
  );
}