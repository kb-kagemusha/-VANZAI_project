import { Link, Navigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { SummaryCard } from "../components/SummaryCard";
import {
  ApiError,
  generateMonthlyBilling,
  getDashboard,
  getProjects,
  hardCloseProject,
  releaseHardCloseProject,
  releaseSoftCloseProject,
  softCloseProject,
} from "../lib/api/client";
import { currentMonthInput, formatDate, formatDateTime, minutesToHours, toPeriodKey } from "../lib/formatters";

type ClosingRowDraft = {
  approver: string;
  reason: string;
};

type AuditLogSearchOptions = {
  projectId?: string;
  quickFilter: string;
  targetType?: string;
  actionType?: string;
};

const CLOSING_SELECTED_INPUTS_STORAGE_KEY = "vanzai.dashboard.closing.selected";
const CLOSING_ROW_DRAFTS_STORAGE_KEY = "vanzai.dashboard.closing.rows";
const CLOSING_SELECTED_ROWS_STORAGE_KEY = "vanzai.dashboard.closing.selectedRows";

function buildAuditLogSearch(periodKey: string, options: AuditLogSearchOptions): string {
  const searchParams = new URLSearchParams();
  searchParams.set("period_key", periodKey);
  searchParams.set("quick_filter", options.quickFilter);
  if (options.projectId) {
    searchParams.set("project_id", options.projectId);
  }
  if (options.targetType) {
    searchParams.set("target_type", options.targetType);
  }
  if (options.actionType) {
    searchParams.set("action_type", options.actionType);
  }
  return searchParams.toString();
}

export function DashboardPage() {
  const [monthValue, setMonthValue] = useState(currentMonthInput());
  const [projectId, setProjectId] = useState("");
  const [selectedReason, setSelectedReason] = useState("");
  const [selectedApprover, setSelectedApprover] = useState("");
  const [rowDrafts, setRowDrafts] = useState<Record<string, ClosingRowDraft>>({});
  const [selectedClosingRows, setSelectedClosingRows] = useState<Record<string, boolean>>({});
  const periodKey = toPeriodKey(monthValue);
  const queryClient = useQueryClient();
  const dashboardQuery = useQuery({
    queryKey: ["dashboard", periodKey],
    queryFn: () => getDashboard(periodKey),
  });
  const projectsQuery = useQuery({
    queryKey: ["projects-all"],
    queryFn: () => getProjects({ limit: 200 }),
  });

  const monthlyBillingMutation = useMutation({
    mutationFn: () => generateMonthlyBilling(periodKey),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["invoices"] });
      void queryClient.invalidateQueries({ queryKey: ["payouts"] });
    },
  });

  const softCloseMutation = useMutation({
    mutationFn: ({ projectId: targetProjectId, reason }: { projectId: string; reason?: string }) =>
      softCloseProject(targetProjectId, periodKey, reason || undefined),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      setSelectedReason("");
    },
  });

  const hardCloseMutation = useMutation({
    mutationFn: ({ projectId: targetProjectId, approver, reason }: { projectId: string; approver: string; reason?: string }) =>
      hardCloseProject(targetProjectId, periodKey, approver, reason || undefined),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      setSelectedReason("");
      setSelectedApprover("");
    },
  });

  const releaseSoftCloseMutation = useMutation({
    mutationFn: ({ projectId: targetProjectId, approver, reason }: { projectId: string; approver: string; reason: string }) =>
      releaseSoftCloseProject(targetProjectId, periodKey, approver, reason),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      setSelectedReason("");
      setSelectedApprover("");
    },
  });

  const releaseHardCloseMutation = useMutation({
    mutationFn: ({ projectId: targetProjectId, approver, reason }: { projectId: string; approver: string; reason: string }) =>
      releaseHardCloseProject(targetProjectId, periodKey, approver, reason),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      setSelectedReason("");
      setSelectedApprover("");
    },
  });

  const getRowDraft = (targetProjectId: string): ClosingRowDraft => rowDrafts[targetProjectId] || { approver: "", reason: "" };
  const isClosingRowSelected = (targetProjectId: string): boolean => Boolean(selectedClosingRows[targetProjectId]);

  useEffect(() => {
    const savedSelectedInputs = window.localStorage.getItem(`${CLOSING_SELECTED_INPUTS_STORAGE_KEY}.${periodKey}`);
    const savedRowDrafts = window.localStorage.getItem(`${CLOSING_ROW_DRAFTS_STORAGE_KEY}.${periodKey}`);
    const savedSelectedRows = window.localStorage.getItem(`${CLOSING_SELECTED_ROWS_STORAGE_KEY}.${periodKey}`);

    if (savedSelectedInputs) {
      try {
        const parsed = JSON.parse(savedSelectedInputs) as ClosingRowDraft;
        setSelectedApprover(parsed.approver || "");
        setSelectedReason(parsed.reason || "");
      } catch {
        setSelectedApprover("");
        setSelectedReason("");
      }
    } else {
      setSelectedApprover("");
      setSelectedReason("");
    }

    if (savedRowDrafts) {
      try {
        setRowDrafts(JSON.parse(savedRowDrafts) as Record<string, ClosingRowDraft>);
      } catch {
        setRowDrafts({});
      }
    } else {
      setRowDrafts({});
    }

    if (savedSelectedRows) {
      try {
        setSelectedClosingRows(JSON.parse(savedSelectedRows) as Record<string, boolean>);
      } catch {
        setSelectedClosingRows({});
      }
    } else {
      setSelectedClosingRows({});
    }
  }, [periodKey]);

  useEffect(() => {
    window.localStorage.setItem(
      `${CLOSING_SELECTED_INPUTS_STORAGE_KEY}.${periodKey}`,
      JSON.stringify({ approver: selectedApprover, reason: selectedReason }),
    );
  }, [periodKey, selectedApprover, selectedReason]);

  useEffect(() => {
    window.localStorage.setItem(`${CLOSING_ROW_DRAFTS_STORAGE_KEY}.${periodKey}`, JSON.stringify(rowDrafts));
  }, [periodKey, rowDrafts]);

  useEffect(() => {
    window.localStorage.setItem(`${CLOSING_SELECTED_ROWS_STORAGE_KEY}.${periodKey}`, JSON.stringify(selectedClosingRows));
  }, [periodKey, selectedClosingRows]);

  const updateRowDraft = (targetProjectId: string, field: keyof ClosingRowDraft, value: string) => {
    setRowDrafts((current) => ({
      ...current,
      [targetProjectId]: {
        approver: current[targetProjectId]?.approver || "",
        reason: current[targetProjectId]?.reason || "",
        [field]: value,
      },
    }));
  };

  const toggleClosingRowSelection = (targetProjectId: string, checked: boolean) => {
    setSelectedClosingRows((current) => ({
      ...current,
      [targetProjectId]: checked,
    }));
  };

  const clearClosingRowSelection = () => {
    setSelectedClosingRows({});
  };

  const selectClosingRowsByStatus = (status: string) => {
    const closingRows = dashboardQuery.data?.closing_status ?? [];
    const nextSelectedRows: Record<string, boolean> = {};

    for (const row of closingRows) {
      if (row.status === status) {
        nextSelectedRows[row.project_id] = true;
      }
    }

    setSelectedClosingRows(nextSelectedRows);
  };

  const selectReleaseTargetRows = () => {
    const closingRows = dashboardQuery.data?.closing_status ?? [];
    const nextSelectedRows: Record<string, boolean> = {};

    for (const row of closingRows) {
      if (row.status === "soft_closed" || row.status === "hard_closed") {
        nextSelectedRows[row.project_id] = true;
      }
    }

    setSelectedClosingRows(nextSelectedRows);
  };

  const selectApproverRequiredRowsWithoutApprover = () => {
    const closingRows = dashboardQuery.data?.closing_status ?? [];
    const nextSelectedRows: Record<string, boolean> = {};

    for (const row of closingRows) {
      const approver = getRowDraft(row.project_id).approver.trim();
      if (row.status !== "open" && approver.length === 0) {
        nextSelectedRows[row.project_id] = true;
      }
    }

    setSelectedClosingRows(nextSelectedRows);
  };

  const selectReasonRequiredRowsWithoutReason = () => {
    const closingRows = dashboardQuery.data?.closing_status ?? [];
    const nextSelectedRows: Record<string, boolean> = {};

    for (const row of closingRows) {
      const reason = getRowDraft(row.project_id).reason.trim();
      if ((row.status === "soft_closed" || row.status === "hard_closed") && reason.length === 0) {
        nextSelectedRows[row.project_id] = true;
      }
    }

    setSelectedClosingRows(nextSelectedRows);
  };

  const getRowsAffectedByCopy = (rows: typeof closingRows) =>
    rows.filter((row) => {
      const draft = getRowDraft(row.project_id);
      const nextApprover = selectedApprover || draft.approver;
      const nextReason = selectedReason || draft.reason;
      return nextApprover !== draft.approver || nextReason !== draft.reason;
    });

  const buildCopyConfirmationMessage = (rows: typeof closingRows, scopeLabel: string) => {
    const affectedRows = getRowsAffectedByCopy(rows);
    if (affectedRows.length === 0) {
      return null;
    }

    const names = affectedRows.slice(0, 5).map((row) => row.project_name);
    const remainingCount = affectedRows.length - names.length;
    const suffix = remainingCount > 0 ? ` ほか${remainingCount}件` : "";
    return `${scopeLabel} ${affectedRows.length}件の入力を上書きします。対象: ${names.join("、")}${suffix}`;
  };

  const copySelectedInputsToRows = () => {
    const closingRows = dashboardQuery.data?.closing_status ?? [];
    const confirmationMessage = buildCopyConfirmationMessage(closingRows, "全行");

    if (!confirmationMessage || !window.confirm(confirmationMessage)) {
      return;
    }

    setRowDrafts((current) => {
      const nextDrafts = { ...current };
      for (const row of closingRows) {
        nextDrafts[row.project_id] = {
          approver: selectedApprover || current[row.project_id]?.approver || "",
          reason: selectedReason || current[row.project_id]?.reason || "",
        };
      }
      return nextDrafts;
    });
  };

  const copySelectedInputsToCheckedRows = () => {
    const closingRows = dashboardQuery.data?.closing_status ?? [];
    const targetRows = closingRows.filter((row) => selectedClosingRows[row.project_id]);
    const confirmationMessage = buildCopyConfirmationMessage(targetRows, "選択行");

    if (!confirmationMessage || !window.confirm(confirmationMessage)) {
      return;
    }

    setRowDrafts((current) => {
      const nextDrafts = { ...current };
      for (const row of closingRows) {
        if (!selectedClosingRows[row.project_id]) {
          continue;
        }
        nextDrafts[row.project_id] = {
          approver: selectedApprover || current[row.project_id]?.approver || "",
          reason: selectedReason || current[row.project_id]?.reason || "",
        };
      }
      return nextDrafts;
    });
  };

  const closingMutationError =
    monthlyBillingMutation.error instanceof ApiError
      ? monthlyBillingMutation.error.message
      : softCloseMutation.error instanceof ApiError
        ? softCloseMutation.error.message
        : hardCloseMutation.error instanceof ApiError
          ? hardCloseMutation.error.message
          : releaseSoftCloseMutation.error instanceof ApiError
            ? releaseSoftCloseMutation.error.message
            : releaseHardCloseMutation.error instanceof ApiError
              ? releaseHardCloseMutation.error.message
              : null;

  if (dashboardQuery.isLoading) {
    return <LoadingOverlay label="ダッシュボードを読み込み中..." />;
  }

  if (dashboardQuery.error instanceof ApiError && dashboardQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (dashboardQuery.isError || !dashboardQuery.data) {
    return <ErrorState title="ダッシュボードの取得に失敗しました" description="API 接続と認証状態を確認してください。" />;
  }

  const closingRows = dashboardQuery.data.closing_status;
  const allCopyAffectedRows = getRowsAffectedByCopy(closingRows);
  const selectedCopyAffectedRows = getRowsAffectedByCopy(closingRows.filter((row) => isClosingRowSelected(row.project_id)));
  const selectedClosingRowCount = closingRows.filter((row) => isClosingRowSelected(row.project_id)).length;
  const allClosingRowsSelected = closingRows.length > 0 && closingRows.every((row) => isClosingRowSelected(row.project_id));
  const selectedRowsMissingApproverCount = closingRows.filter((row) => isClosingRowSelected(row.project_id) && getRowDraft(row.project_id).approver.trim().length === 0).length;
  const selectedReleaseRowsMissingReasonCount = closingRows.filter(
    (row) => isClosingRowSelected(row.project_id) && (row.status === "soft_closed" || row.status === "hard_closed") && getRowDraft(row.project_id).reason.trim().length === 0,
  ).length;

  const toggleAllClosingRows = (checked: boolean) => {
    if (!checked) {
      clearClosingRowSelection();
      return;
    }

    const nextSelectedRows: Record<string, boolean> = {};
    for (const row of closingRows) {
      nextSelectedRows[row.project_id] = true;
    }
    setSelectedClosingRows(nextSelectedRows);
  };

  const findCount = (itemType: string) =>
    dashboardQuery.data?.unprocessed_items.find((item) => item.item_type === itemType)?.count ?? 0;

  return (
    <div className="page-stack">
      <PageHeader title="ダッシュボード" description="未処理、差異、締め状況を月次単位で確認し、そのまま月次処理を進めます。" eyebrow="月次運用" />
      <FilterBar>
        <label>
          対象月
          <input type="month" value={monthValue} onChange={(event) => setMonthValue(event.target.value)} />
        </label>
      </FilterBar>

      <section className="upload-card">
        <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "center", flexWrap: "wrap" }}>
          <div>
            <h3 className="section-title">月次一括生成</h3>
            <p style={{ margin: 0, color: "var(--color-muted)" }}>対象月の請求書と支払明細をまとめて生成します。</p>
          </div>
          <button onClick={() => monthlyBillingMutation.mutate()} disabled={monthlyBillingMutation.isPending}>
            {monthlyBillingMutation.isPending ? "実行中..." : "月次一括生成"}
          </button>
        </div>
        {monthlyBillingMutation.isSuccess ? (
          <p style={{ margin: 0 }}>
            請求 {monthlyBillingMutation.data.generated_invoices} 件生成 / {monthlyBillingMutation.data.skipped_invoices} 件スキップ、
            支払 {monthlyBillingMutation.data.generated_payouts} 件生成 / {monthlyBillingMutation.data.skipped_payouts} 件スキップ
          </p>
        ) : null}
        {monthlyBillingMutation.error instanceof ApiError ? (
          <p style={{ margin: 0, color: "var(--color-danger, #b42318)" }}>{monthlyBillingMutation.error.message}</p>
        ) : null}
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <Link to={{ pathname: "/audit-logs", search: `?${buildAuditLogSearch(periodKey, { quickFilter: "invoice_all" })}` }}>
            請求ログを見る
          </Link>
          <Link to={{ pathname: "/audit-logs", search: `?${buildAuditLogSearch(periodKey, { quickFilter: "payout_all" })}` }}>
            支払ログを見る
          </Link>
        </div>
      </section>

      <section className="upload-card">
        <div>
          <h3 className="section-title">締め処理</h3>
          <p style={{ marginTop: 0, color: "var(--color-muted)" }}>案件を選んで仮締め・本締めを実行します。</p>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.75rem" }}>
          <label>
            案件
            <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
              <option value="">案件を選択</option>
              {(projectsQuery.data?.items ?? []).map((project) => (
                <option key={project.id} value={project.id}>{project.name}</option>
              ))}
            </select>
          </label>
          <label>
            締め理由
            <input value={selectedReason} onChange={(event) => setSelectedReason(event.target.value)} placeholder="任意" />
          </label>
          <label>
            承認者
            <input value={selectedApprover} onChange={(event) => setSelectedApprover(event.target.value)} placeholder="本締めで必須" />
          </label>
        </div>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <Link to={{ pathname: "/audit-logs", search: `?${buildAuditLogSearch(periodKey, { projectId: projectId || undefined, quickFilter: "closing_all" })}` }}>
            締め関連ログ
          </Link>
          <Link to={{ pathname: "/audit-logs", search: `?${buildAuditLogSearch(periodKey, { projectId: projectId || undefined, quickFilter: "closing_execute" })}` }}>
            締め実行ログ
          </Link>
          <Link to={{ pathname: "/audit-logs", search: `?${buildAuditLogSearch(periodKey, { projectId: projectId || undefined, quickFilter: "closing_release" })}` }}>
            締め解除ログ
          </Link>
        </div>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <button onClick={() => softCloseMutation.mutate({ projectId, reason: selectedReason })} disabled={!projectId || softCloseMutation.isPending}>
            {softCloseMutation.isPending ? "仮締め中..." : "仮締め"}
          </button>
          <button onClick={() => hardCloseMutation.mutate({ projectId, approver: selectedApprover, reason: selectedReason })} disabled={!projectId || !selectedApprover || hardCloseMutation.isPending}>
            {hardCloseMutation.isPending ? "本締め中..." : "本締め"}
          </button>
          <button onClick={copySelectedInputsToRows} disabled={allCopyAffectedRows.length === 0}>
            一覧へ入力コピー
          </button>
          <button onClick={copySelectedInputsToCheckedRows} disabled={selectedClosingRowCount === 0 || selectedCopyAffectedRows.length === 0}>
            選択行へ入力コピー
          </button>
          <button onClick={clearClosingRowSelection} disabled={selectedClosingRowCount === 0}>
            選択解除
          </button>
        </div>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <button onClick={() => selectClosingRowsByStatus("open")} disabled={closingRows.length === 0}>
            未締めを選択
          </button>
          <button onClick={() => selectClosingRowsByStatus("soft_closed")} disabled={closingRows.length === 0}>
            仮締め済みを選択
          </button>
          <button onClick={() => selectClosingRowsByStatus("hard_closed")} disabled={closingRows.length === 0}>
            本締め済みを選択
          </button>
          <button onClick={selectReleaseTargetRows} disabled={closingRows.length === 0}>
            解除候補を選択
          </button>
          <button onClick={selectApproverRequiredRowsWithoutApprover} disabled={closingRows.length === 0}>
            承認者未入力の必須行を選択
          </button>
          <button onClick={selectReasonRequiredRowsWithoutReason} disabled={closingRows.length === 0}>
            理由未入力の解除候補を選択
          </button>
        </div>
        {(allCopyAffectedRows.length > 0 || selectedCopyAffectedRows.length > 0) ? (
          <div style={{ display: "grid", gap: "0.35rem", padding: "0.75rem", border: "1px solid var(--color-border, #d0d5dd)", borderRadius: "0.75rem", background: "rgba(15, 23, 42, 0.02)" }}>
            <strong>入力コピーの確認</strong>
            <span>全行コピー: {allCopyAffectedRows.length} 件を更新予定</span>
            {allCopyAffectedRows.length > 0 ? <span>対象案件: {allCopyAffectedRows.slice(0, 5).map((row) => row.project_name).join("、")}{allCopyAffectedRows.length > 5 ? ` ほか${allCopyAffectedRows.length - 5}件` : ""}</span> : null}
            <span>選択行コピー: {selectedCopyAffectedRows.length} 件を更新予定</span>
            {selectedCopyAffectedRows.length > 0 ? <span>対象案件: {selectedCopyAffectedRows.slice(0, 5).map((row) => row.project_name).join("、")}{selectedCopyAffectedRows.length > 5 ? ` ほか${selectedCopyAffectedRows.length - 5}件` : ""}</span> : null}
          </div>
        ) : null}
        <div style={{ display: "grid", gap: "0.35rem", padding: "0.75rem", border: "1px solid var(--color-border, #d0d5dd)", borderRadius: "0.75rem" }}>
          <strong>選択状態</strong>
          <span>選択行: {selectedClosingRowCount} 件</span>
          <span>承認者未入力: {selectedRowsMissingApproverCount} 件</span>
          <span>解除理由未入力: {selectedReleaseRowsMissingReasonCount} 件</span>
        </div>
        <p style={{ margin: 0, color: "var(--color-muted)" }}>選択中の承認者・理由は月ごとに保持されます。全行コピーに加えて、チェックした {selectedClosingRowCount} 件だけへ反映できます。</p>
        {closingMutationError ? <p style={{ margin: 0, color: "var(--color-danger, #b42318)" }}>{closingMutationError}</p> : null}
        {softCloseMutation.isSuccess ? <p style={{ margin: 0 }}>仮締めを実行しました。</p> : null}
        {hardCloseMutation.isSuccess ? <p style={{ margin: 0 }}>本締めを実行しました。</p> : null}
        {releaseSoftCloseMutation.isSuccess ? <p style={{ margin: 0 }}>仮締め解除を実行しました。</p> : null}
        {releaseHardCloseMutation.isSuccess ? <p style={{ margin: 0 }}>本締め解除を実行しました。</p> : null}
      </section>

      <section className="summary-grid">
        <SummaryCard label="差異アサイン" value={findCount("assignment_variance")} accent="#c8553d" />
        <SummaryCard label="単価未設定" value={findCount("missing_price")} accent="#d98f2b" />
        <SummaryCard label="未発行請求" value={findCount("unissued_invoice")} accent="#2a6f97" />
        <SummaryCard label="未処理支払" value={findCount("unprocessed_payout")} accent="#4a7c59" />
        <SummaryCard label="未締め案件" value={findCount("unclosed_projects")} accent="#6a4c93" />
      </section>

      <section className="two-column-grid">
        <div>
          <h3 className="section-title">差異アラート</h3>
          <DataTable
            columns={[
              { key: "project", header: "案件", render: (row) => row.project_name },
              { key: "worker", header: "稼働者", render: (row) => row.worker_name },
              { key: "date", header: "日付", render: (row) => formatDate(row.work_date) },
              { key: "planned", header: "予定", render: (row) => minutesToHours(row.planned_minutes) },
              { key: "actual", header: "実績", render: (row) => minutesToHours(row.actual_minutes) },
              { key: "variance", header: "差分", render: (row) => minutesToHours(row.variance_minutes) },
            ]}
            rows={dashboardQuery.data.variance_alerts}
            getRowKey={(row) => `${row.project_name}-${row.worker_name}-${row.work_date}`}
            emptyTitle="差異アラートはありません"
            emptyDescription="予定と実績の差分は現時点で検知されていません。"
          />
        </div>

        <div>
          <h3 className="section-title">締め状況</h3>
          <DataTable
            columns={[
              {
                key: "copyTarget",
                header: (
                  <label style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                    <input
                      type="checkbox"
                      aria-label="締め状況の全行を選択"
                      checked={allClosingRowsSelected}
                      onChange={(event) => toggleAllClosingRows(event.target.checked)}
                    />
                    <span>コピー対象</span>
                  </label>
                ),
                render: (row) => (
                  <input
                    type="checkbox"
                    aria-label={`${row.project_name} をコピー対象にする`}
                    checked={isClosingRowSelected(row.project_id)}
                    onChange={(event) => toggleClosingRowSelection(row.project_id, event.target.checked)}
                  />
                ),
              },
              { key: "project", header: "案件", render: (row) => row.project_name },
              { key: "period", header: "対象月", render: (row) => row.period_key },
              { key: "status", header: "状態", render: (row) => <StatusBadge value={row.status} /> },
              { key: "closedAt", header: "締め日時", render: (row) => formatDateTime(row.closed_at) },
              { key: "closedBy", header: "実行者", render: (row) => row.closed_by || "-" },
              { key: "releaseCount", header: "解除回数", render: (row) => row.release_count },
              { key: "releasedBy", header: "最終解除者", render: (row) => row.last_released_by || "-" },
              { key: "deadline", header: "再締め期限", render: (row) => formatDateTime(row.reclose_deadline) },
              {
                key: "rowApprover",
                header: "承認者入力",
                render: (row) => (
                  <input
                    value={getRowDraft(row.project_id).approver}
                    onChange={(event) => updateRowDraft(row.project_id, "approver", event.target.value)}
                    placeholder="username"
                  />
                ),
              },
              {
                key: "rowReason",
                header: "理由入力",
                render: (row) => (
                  <input
                    value={getRowDraft(row.project_id).reason}
                    onChange={(event) => updateRowDraft(row.project_id, "reason", event.target.value)}
                    placeholder={row.status === "open" ? "任意" : "必須"}
                  />
                ),
              },
              {
                key: "actions",
                header: "操作",
                render: (row) => (
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    <Link to={{ pathname: "/audit-logs", search: `?${buildAuditLogSearch(row.period_key, { projectId: row.project_id, quickFilter: "closing_all" })}` }}>
                      監査ログ
                    </Link>
                    <Link to={{ pathname: "/audit-logs", search: `?${buildAuditLogSearch(row.period_key, { projectId: row.project_id, quickFilter: "closing_execute" })}` }}>
                      実行ログ
                    </Link>
                    {(row.status === "soft_closed" || row.status === "hard_closed") ? (
                      <Link to={{ pathname: "/audit-logs", search: `?${buildAuditLogSearch(row.period_key, { projectId: row.project_id, quickFilter: "closing_release" })}` }}>
                        解除ログ
                      </Link>
                    ) : null}
                    {row.status === "open" ? (
                      <button
                        onClick={() => {
                          setProjectId(row.project_id);
                          softCloseMutation.mutate({ projectId: row.project_id, reason: getRowDraft(row.project_id).reason });
                        }}
                        disabled={softCloseMutation.isPending}
                      >
                        仮締め
                      </button>
                    ) : null}
                    {row.status === "soft_closed" ? (
                      <>
                        <button
                          onClick={() => {
                            setProjectId(row.project_id);
                            hardCloseMutation.mutate({
                              projectId: row.project_id,
                              approver: getRowDraft(row.project_id).approver,
                              reason: getRowDraft(row.project_id).reason,
                            });
                          }}
                          disabled={!getRowDraft(row.project_id).approver || hardCloseMutation.isPending}
                        >
                          本締め
                        </button>
                        <button
                          onClick={() => releaseSoftCloseMutation.mutate({
                            projectId: row.project_id,
                            approver: getRowDraft(row.project_id).approver,
                            reason: getRowDraft(row.project_id).reason,
                          })}
                          disabled={!getRowDraft(row.project_id).approver || !getRowDraft(row.project_id).reason || releaseSoftCloseMutation.isPending}
                        >
                          仮締め解除
                        </button>
                      </>
                    ) : null}
                    {row.status === "hard_closed" ? (
                      <button
                        onClick={() => releaseHardCloseMutation.mutate({
                          projectId: row.project_id,
                          approver: getRowDraft(row.project_id).approver,
                          reason: getRowDraft(row.project_id).reason,
                        })}
                        disabled={!getRowDraft(row.project_id).approver || !getRowDraft(row.project_id).reason || releaseHardCloseMutation.isPending}
                      >
                        本締め解除
                      </button>
                    ) : null}
                  </div>
                ),
              },
            ]}
            rows={closingRows}
            getRowKey={(row) => `${row.project_name}-${row.period_key}`}
            emptyTitle="締めレコードはありません"
            emptyDescription="対象月の締め状況はまだ作成されていません。"
          />
        </div>
      </section>
    </div>
  );
}