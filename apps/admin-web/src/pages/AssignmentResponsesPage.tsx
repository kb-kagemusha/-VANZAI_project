import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate, useSearchParams } from "react-router-dom";
import { useEffect, useState } from "react";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { PaginationBar } from "../components/PaginationBar";
import { SummaryCard } from "../components/SummaryCard";
import { ApiError, getAssignmentEscalationHistory, getAssignmentReminderHistory, getAssignments, getProjects, getWorkers, sendAssignmentEscalations, sendAssignmentReminders } from "../lib/api/client";
import { currentMonthInput, formatDate, formatDateTime, periodKeyToDateRange, toPeriodKey } from "../lib/formatters";

const PAGE_SIZE = 20;

function monitoringLabel(value: string | null): string {
  if (value === "escalate") {
    return "要対応";
  }
  if (value === "watch") {
    return "監視中";
  }
  return "-";
}

export function AssignmentResponsesPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedRows, setSelectedRows] = useState<Record<string, boolean>>({});
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const monthParam = searchParams.get("month") || currentMonthInput();
  const monitoringParam = searchParams.get("monitoring") || "";
  const missingEmailParam = searchParams.get("missing_email") === "true";
  const projectParam = searchParams.get("project_id") || "";
  const workerParam = searchParams.get("worker_id") || "";
  const pageParam = Number(searchParams.get("page") || "0");

  const periodKey = toPeriodKey(monthParam);
  const { from: workDateFrom, to: workDateTo } = periodKeyToDateRange(periodKey);

  const assignmentsQuery = useQuery({
    queryKey: ["assignment-responses", periodKey, projectParam, workerParam, monitoringParam, missingEmailParam, pageParam],
    queryFn: () =>
      getAssignments({
        response_status: "pending",
        project_id: projectParam || undefined,
        worker_id: workerParam || undefined,
        monitoring_status: monitoringParam || undefined,
        missing_email_only: missingEmailParam || undefined,
        work_date_from: workDateFrom,
        work_date_to: workDateTo,
        sort_by: "work_date",
        sort_order: "asc",
        offset: pageParam * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  });

  const pendingSummaryQuery = useQuery({
    queryKey: ["assignment-responses-summary", periodKey, "all"],
    queryFn: () => getAssignments({ response_status: "pending", work_date_from: workDateFrom, work_date_to: workDateTo, offset: 0, limit: 1 }),
  });

  const escalatedSummaryQuery = useQuery({
    queryKey: ["assignment-responses-summary", periodKey, "escalate"],
    queryFn: () => getAssignments({ response_status: "pending", monitoring_status: "escalate", work_date_from: workDateFrom, work_date_to: workDateTo, offset: 0, limit: 1 }),
  });

  const missingEmailSummaryQuery = useQuery({
    queryKey: ["assignment-responses-summary", periodKey, "missing-email"],
    queryFn: () => getAssignments({ response_status: "pending", missing_email_only: true, work_date_from: workDateFrom, work_date_to: workDateTo, offset: 0, limit: 1 }),
  });

  const projectsQuery = useQuery({
    queryKey: ["projects-assignment-responses"],
    queryFn: () => getProjects({ limit: 200, is_active: true, sort_by: "name", sort_order: "asc" }),
  });

  const workersQuery = useQuery({
    queryKey: ["workers-assignment-responses"],
    queryFn: () => getWorkers({ limit: 200, is_active: true, sort_by: "name", sort_order: "asc" }),
  });

  const currentRows = assignmentsQuery.data?.items ?? [];
  const currentRowIds = currentRows.map((row) => row.id);

  const reminderHistoryQuery = useQuery({
    queryKey: ["assignment-response-reminder-history", ...currentRowIds],
    enabled: currentRowIds.length > 0,
    queryFn: () => getAssignmentReminderHistory({ assignment_ids: currentRowIds, limit: 20 }),
  });

  const escalationHistoryQuery = useQuery({
    queryKey: ["assignment-response-escalation-history", ...currentRowIds],
    enabled: currentRowIds.length > 0,
    queryFn: () => getAssignmentEscalationHistory({ assignment_ids: currentRowIds, limit: 20 }),
  });

  useEffect(() => {
    setSelectedRows({});
  }, [monthParam, monitoringParam, missingEmailParam, projectParam, workerParam, pageParam]);

  const reminderMutation = useMutation({
    mutationFn: (assignmentIds: string[]) => sendAssignmentReminders({ assignment_ids: assignmentIds }),
    onSuccess: async (result) => {
      setActionError("");
      setSelectedRows({});
      setActionMessage(
        `催促送信を実行しました: 対象${result.eligible_assignment_count}件 / sent ${result.sent_count} / failed ${result.failed_count} / missing email ${result.skipped_missing_email_count}${result.dry_run ? " / dry-run" : ""}`,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["assignment-response-reminder-history"] }),
        queryClient.invalidateQueries({ queryKey: ["assignment-response-escalation-history"] }),
        queryClient.invalidateQueries({ queryKey: ["assignment-responses"] }),
        queryClient.invalidateQueries({ queryKey: ["assignment-responses-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
    },
    onError: (error: unknown) => {
      setActionMessage("");
      setActionError(error instanceof ApiError ? error.message : "予定確認催促の送信に失敗しました");
    },
  });

  const escalationMutation = useMutation({
    mutationFn: (assignmentIds: string[]) => sendAssignmentEscalations({ assignment_ids: assignmentIds }),
    onSuccess: async (result) => {
      setActionError("");
      setSelectedRows({});
      setActionMessage(
        `管理者通知を実行しました: 対象${result.eligible_assignment_count}件 / recipient ${result.recipient_count} / sent ${result.sent_count} / failed ${result.failed_count}${result.dry_run ? " / dry-run" : ""}`,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["assignment-response-reminder-history"] }),
        queryClient.invalidateQueries({ queryKey: ["assignment-response-escalation-history"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
    },
    onError: (error: unknown) => {
      setActionMessage("");
      setActionError(error instanceof ApiError ? error.message : "管理者通知の送信に失敗しました");
    },
  });

  const updateSearchParams = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(updates)) {
      if (!value) {
        next.delete(key);
      } else {
        next.set(key, value);
      }
    }
    if (!updates.page) {
      next.set("page", "0");
    }
    setSearchParams(next);
  };

  if (assignmentsQuery.isLoading) {
    return <LoadingOverlay label="予定確認監視を読み込み中..." />;
  }

  if (assignmentsQuery.error instanceof ApiError && assignmentsQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (assignmentsQuery.isError || !assignmentsQuery.data) {
    return <ErrorState title="予定確認監視の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  const selectedAssignmentIds = currentRows.filter((row) => selectedRows[row.id]).map((row) => row.id);
  const selectedEscalatedAssignmentIds = currentRows
    .filter((row) => selectedRows[row.id] && row.monitoring_status === "escalate")
    .map((row) => row.id);
  const allRowsSelected = currentRows.length > 0 && currentRows.every((row) => selectedRows[row.id]);

  const toggleAllRows = (checked: boolean) => {
    const next: Record<string, boolean> = {};
    for (const row of currentRows) {
      next[row.id] = checked;
    }
    setSelectedRows(next);
  };

  const submitReminder = (assignmentIds: string[]) => {
    if (assignmentIds.length === 0) {
      return;
    }
    reminderMutation.mutate(assignmentIds);
  };

  return (
    <div className="page-stack">
      <PageHeader title="予定確認監視" description="未回答の予定確認を month 単位で監視し、要対応対象を抽出します。" eyebrow="月次運用" />

      <section className="summary-grid">
        <SummaryCard label="未回答" value={pendingSummaryQuery.data?.total ?? 0} accent="#0f766e" />
        <SummaryCard label="要対応" value={escalatedSummaryQuery.data?.total ?? 0} accent="#9f1239" />
        <SummaryCard label="メール未設定" value={missingEmailSummaryQuery.data?.total ?? 0} accent="#b42318" />
      </section>

      <FilterBar>
        <label>
          対象月
          <input type="month" value={monthParam} onChange={(event) => updateSearchParams({ month: event.target.value, page: "0" })} />
        </label>
        <label>
          案件
          <select value={projectParam} onChange={(event) => updateSearchParams({ project_id: event.target.value || null, page: "0" })}>
            <option value="">すべて</option>
            {(projectsQuery.data?.items ?? []).map((project) => (
              <option key={project.id} value={project.id}>{project.name}</option>
            ))}
          </select>
        </label>
        <label>
          稼働者
          <select value={workerParam} onChange={(event) => updateSearchParams({ worker_id: event.target.value || null, page: "0" })}>
            <option value="">すべて</option>
            {(workersQuery.data?.items ?? []).map((worker) => (
              <option key={worker.id} value={worker.id}>{worker.name}</option>
            ))}
          </select>
        </label>
        <label>
          監視状態
          <select value={monitoringParam} onChange={(event) => updateSearchParams({ monitoring: event.target.value || null, page: "0" })}>
            <option value="">すべて</option>
            <option value="watch">監視中</option>
            <option value="escalate">要対応</option>
          </select>
        </label>
        <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <input
            type="checkbox"
            checked={missingEmailParam}
            onChange={(event) => updateSearchParams({ missing_email: event.target.checked ? "true" : null, page: "0" })}
          />
          メール未設定のみ
        </label>
      </FilterBar>

      <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
          <strong>催促再送</strong>
          <span>このページで {selectedAssignmentIds.length} 件選択中</span>
        </div>
        <p style={{ margin: 0, color: "var(--color-text-subtle, #667085)" }}>
          未回答 assignment を worker 単位で束ねて再送します。送信可否はサーバーの EMAIL_DRY_RUN 設定に従います。
        </p>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <button type="button" onClick={() => toggleAllRows(true)} disabled={currentRows.length === 0}>このページを全選択</button>
          <button type="button" onClick={() => toggleAllRows(false)} disabled={selectedAssignmentIds.length === 0}>選択解除</button>
          <button type="button" onClick={() => submitReminder(selectedAssignmentIds)} disabled={selectedAssignmentIds.length === 0 || reminderMutation.isPending}>
            {reminderMutation.isPending ? "送信中..." : "選択中へ催促送信"}
          </button>
          <button type="button" onClick={() => escalationMutation.mutate(selectedEscalatedAssignmentIds)} disabled={selectedEscalatedAssignmentIds.length === 0 || escalationMutation.isPending}>
            {escalationMutation.isPending ? "通知中..." : "選択中の要対応を管理者へ通知"}
          </button>
        </div>
        {actionMessage ? <p style={{ margin: 0 }}>{actionMessage}</p> : null}
        {actionError ? <p className="form-error">{actionError}</p> : null}
      </section>

      <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
          <strong>直近催促履歴</strong>
          <span>このページに表示中の assignment に紐づく直近 20 件</span>
        </div>
        <DataTable
          columns={[
            { key: "createdAt", header: "実行日時", render: (row) => formatDateTime(row.created_at) },
            { key: "worker", header: "送信先", render: (row) => `${row.worker_name}${row.worker_email ? ` / ${row.worker_email}` : " / 未設定"}` },
            { key: "status", header: "結果", render: (row) => <span className={`status-badge ${row.status === "failed" ? "attention" : "positive"}`}>{row.status === "failed" ? "失敗" : "送信済み"}</span> },
            { key: "actor", header: "実行者", render: (row) => row.actor || "-" },
            { key: "dryRun", header: "dry-run", render: (row) => (row.dry_run ? "yes" : "no") },
            { key: "count", header: "対象件数", render: (row) => row.assignment_count },
          ]}
          rows={reminderHistoryQuery.data?.items ?? []}
          getRowKey={(row) => row.audit_log_id}
          emptyTitle="催促履歴はありません"
          emptyDescription="このページの assignment に対する催促履歴はまだ記録されていません。"
        />
      </section>

      <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
          <strong>直近管理者通知履歴</strong>
          <span>このページに表示中の assignment に紐づく直近 20 件</span>
        </div>
        <DataTable
          columns={[
            { key: "createdAt", header: "実行日時", render: (row) => formatDateTime(row.created_at) },
            { key: "recipient", header: "通知先", render: (row) => `${row.recipient_name} / ${row.recipient_email}` },
            { key: "status", header: "結果", render: (row) => <span className={`status-badge ${row.status === "failed" ? "attention" : "positive"}`}>{row.status === "failed" ? "失敗" : "送信済み"}</span> },
            { key: "actor", header: "実行者", render: (row) => row.actor || "-" },
            { key: "dryRun", header: "dry-run", render: (row) => (row.dry_run ? "yes" : "no") },
            { key: "count", header: "対象件数", render: (row) => row.assignment_count },
          ]}
          rows={escalationHistoryQuery.data?.items ?? []}
          getRowKey={(row) => row.audit_log_id}
          emptyTitle="管理者通知履歴はありません"
          emptyDescription="このページの assignment に対する管理者通知履歴はまだ記録されていません。"
        />
      </section>

      <DataTable
        columns={[
          {
            key: "select",
            header: (
              <input
                type="checkbox"
                aria-label="予定確認監視の全行を選択"
                checked={allRowsSelected}
                onChange={(event) => toggleAllRows(event.target.checked)}
              />
            ),
            render: (row) => (
              <input
                type="checkbox"
                aria-label={`${row.worker_name} の予定確認を選択`}
                checked={Boolean(selectedRows[row.id])}
                onChange={(event) => setSelectedRows((current) => ({ ...current, [row.id]: event.target.checked }))}
              />
            ),
          },
          { key: "project", header: "案件", render: (row) => row.project_name },
          { key: "worker", header: "稼働者", render: (row) => row.worker_name },
          { key: "email", header: "メール", render: (row) => row.worker_email || "未設定" },
          { key: "workDate", header: "稼働日", render: (row) => formatDate(row.work_date) },
          { key: "shift", header: "シフト", render: (row) => row.shift_label || "-" },
          { key: "requested", header: "依頼日時", render: (row) => formatDateTime(row.worker_response_requested_at) },
          { key: "elapsed", header: "経過", render: (row) => (row.hours_since_response_request === null ? "-" : `${row.hours_since_response_request}h`) },
          { key: "until", header: "稼働まで", render: (row) => (row.days_until_work === null ? "-" : `${row.days_until_work}日`) },
          {
            key: "status",
            header: "監視状態",
            render: (row) => (
              <span className={`status-badge ${row.monitoring_status === "escalate" ? "attention" : "neutral"}`}>
                {monitoringLabel(row.monitoring_status)}
              </span>
            ),
          },
          { key: "reasons", header: "条件", render: (row) => row.monitoring_reasons.length > 0 ? row.monitoring_reasons.join(" / ") : "継続確認中" },
          {
            key: "actions",
            header: "操作",
            render: (row) => (
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                <button type="button" onClick={() => submitReminder([row.id])} disabled={reminderMutation.isPending}>
                  再送
                </button>
                {row.monitoring_status === "escalate" ? (
                  <button type="button" onClick={() => escalationMutation.mutate([row.id])} disabled={escalationMutation.isPending}>
                    通知
                  </button>
                ) : null}
              </div>
            ),
          },
        ]}
        rows={assignmentsQuery.data.items}
        getRowKey={(row) => row.id}
        emptyTitle="未回答の予定確認はありません"
        emptyDescription="条件に一致する pending assignment はありません。"
      />

      <PaginationBar
        page={pageParam}
        total={assignmentsQuery.data.total}
        limit={PAGE_SIZE}
        onPrevious={() => updateSearchParams({ page: String(Math.max(pageParam - 1, 0)) })}
        onNext={() => updateSearchParams({ page: String(pageParam + 1) })}
      />
    </div>
  );
}