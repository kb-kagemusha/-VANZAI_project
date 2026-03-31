import { Navigate } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { PaginationBar } from "../components/PaginationBar";
import { StatusBadge } from "../components/StatusBadge";
import { ApiError, bulkUpdateAssignmentStatus, createAssignment, createAssignmentSelectionSet, deleteAssignmentSelectionSet, getAssignmentCancellationHistory, getAssignmentSelectionSets, getAssignments, getProjects, getRoles, getShiftSlots, getWorkers, searchAuditLogs, updateAssignment, updateAssignmentStatus } from "../lib/api/client";
import { useAuth } from "../lib/auth/auth-context";
import { currentMonthInput, formatAuditAction, formatAuditSummary, formatCurrency, formatDate, formatDateTime, periodKeyToDateRange, toPeriodKey } from "../lib/formatters";
import type { AssignmentListItem, AssignmentSelectionSetItem } from "../types/api";

const PAGE_SIZE = 20;
const ASSIGNMENTS_SELECTED_ROWS_STORAGE_KEY = "vanzai.assignments.selectedRows";

export function AssignmentsPage() {
  const { user } = useAuth();
  const [monthValue, setMonthValue] = useState(currentMonthInput());
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [createProjectId, setCreateProjectId] = useState("");
  const [createShiftSlotId, setCreateShiftSlotId] = useState("");
  const [createWorkerId, setCreateWorkerId] = useState("");
  const [createRoleId, setCreateRoleId] = useState("");
  const [createStatus, setCreateStatus] = useState<"tentative" | "confirmed">("tentative");
  const [createLockedPriceSales, setCreateLockedPriceSales] = useState("");
  const [createLockedPriceOutsource, setCreateLockedPriceOutsource] = useState("");
  const [formError, setFormError] = useState("");
  const [editingAssignment, setEditingAssignment] = useState<AssignmentListItem | null>(null);
  const [editShiftSlotId, setEditShiftSlotId] = useState("");
  const [editWorkerId, setEditWorkerId] = useState("");
  const [editRoleId, setEditRoleId] = useState("");
  const [editLockedPriceSales, setEditLockedPriceSales] = useState("");
  const [editLockedPriceOutsource, setEditLockedPriceOutsource] = useState("");
  const [editError, setEditError] = useState("");
  const [selectedAssignmentRows, setSelectedAssignmentRows] = useState<Record<string, boolean>>({});
  const [selectionSetName, setSelectionSetName] = useState("");
  const [selectionSetShared, setSelectionSetShared] = useState(false);
  const [selectionSetError, setSelectionSetError] = useState("");
  const [bulkNextStatus, setBulkNextStatus] = useState<"tentative" | "confirmed" | "canceled">("confirmed");
  const [bulkCancelReason, setBulkCancelReason] = useState("");
  const [bulkReopenReason, setBulkReopenReason] = useState("");
  const [bulkError, setBulkError] = useState("");
  const [selectedAssignment, setSelectedAssignment] = useState<AssignmentListItem | null>(null);
  const [nextStatus, setNextStatus] = useState<"tentative" | "confirmed" | "canceled">("confirmed");
  const [cancelReason, setCancelReason] = useState("");
  const [reopenReason, setReopenReason] = useState("");
  const [actionError, setActionError] = useState("");
  const periodKey = toPeriodKey(monthValue);
  const { from: workDateFrom, to: workDateTo } = periodKeyToDateRange(periodKey);
  const queryClient = useQueryClient();
  const canShareSelectionSet = user?.role === "admin" || user?.role === "ops";

  const assignmentsQuery = useQuery({
    queryKey: ["assignments", periodKey, status, page],
    queryFn: () =>
      getAssignments({
        status: status || undefined,
        work_date_from: workDateFrom,
        work_date_to: workDateTo,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
      placeholderData: keepPreviousData,
  });

  const projectsQuery = useQuery({
    queryKey: ["projects-assignments-form"],
    queryFn: () => getProjects({ limit: 200, is_active: true, sort_by: "name", sort_order: "asc" }),
  });

  const shiftSlotsQuery = useQuery({
    queryKey: ["shift-slots-assignments-form", createProjectId, workDateFrom, workDateTo],
    queryFn: () =>
      getShiftSlots({
        project_id: createProjectId || undefined,
        work_date_from: workDateFrom,
        work_date_to: workDateTo,
        sort_by: "work_date",
        sort_order: "asc",
        limit: 200,
      }),
  });

  const editShiftSlotsQuery = useQuery({
    queryKey: ["shift-slots-assignments-edit", workDateFrom, workDateTo],
    queryFn: () =>
      getShiftSlots({
        work_date_from: workDateFrom,
        work_date_to: workDateTo,
        sort_by: "work_date",
        sort_order: "asc",
        limit: 200,
      }),
  });

  const workersQuery = useQuery({
    queryKey: ["workers-assignments-form"],
    queryFn: () => getWorkers({ limit: 200, sort_by: "name", sort_order: "asc", is_active: true }),
  });

  const rolesQuery = useQuery({
    queryKey: ["roles-assignments-form"],
    queryFn: () => getRoles({ limit: 200, sort_by: "name", sort_order: "asc" }),
  });

  useEffect(() => {
    if (!createProjectId && projectsQuery.data?.items.length) {
      setCreateProjectId(projectsQuery.data.items[0].id);
    }
  }, [createProjectId, projectsQuery.data]);

  useEffect(() => {
    if (!createWorkerId && workersQuery.data?.items.length) {
      setCreateWorkerId(workersQuery.data.items[0].id);
    }
  }, [createWorkerId, workersQuery.data]);

  useEffect(() => {
    if (!createRoleId && rolesQuery.data?.items.length) {
      setCreateRoleId(rolesQuery.data.items[0].id);
    }
  }, [createRoleId, rolesQuery.data]);

  useEffect(() => {
    if (shiftSlotsQuery.data?.items.length) {
      setCreateShiftSlotId((current) => current || shiftSlotsQuery.data.items[0].id);
      return;
    }
    setCreateShiftSlotId("");
  }, [shiftSlotsQuery.data]);

  useEffect(() => {
    const savedSelectedRows = window.localStorage.getItem(`${ASSIGNMENTS_SELECTED_ROWS_STORAGE_KEY}.${periodKey}`);

    if (savedSelectedRows) {
      try {
        setSelectedAssignmentRows(JSON.parse(savedSelectedRows) as Record<string, boolean>);
      } catch {
        setSelectedAssignmentRows({});
      }
    } else {
      setSelectedAssignmentRows({});
    }

    setSelectionSetName("");
    setSelectionSetShared(false);
    setSelectionSetError("");
    setBulkCancelReason("");
    setBulkReopenReason("");
    setBulkError("");
  }, [periodKey]);

  useEffect(() => {
    window.localStorage.setItem(`${ASSIGNMENTS_SELECTED_ROWS_STORAGE_KEY}.${periodKey}`, JSON.stringify(selectedAssignmentRows));
  }, [periodKey, selectedAssignmentRows]);

  const createMutation = useMutation({
    mutationFn: () =>
      createAssignment({
        shift_slot_id: createShiftSlotId,
        worker_id: createWorkerId,
        role_id: createRoleId,
        status: createStatus,
        cancel_reason: null,
        locked_price_sales: createLockedPriceSales || null,
        locked_price_outsource: createLockedPriceOutsource || null,
      }),
    onSuccess: async () => {
      setFormError("");
      setCreateLockedPriceSales("");
      setCreateLockedPriceOutsource("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["assignments"] }),
        queryClient.invalidateQueries({ queryKey: ["shift-slots"] }),
      ]);
    },
    onError: (error: unknown) => {
      setFormError(error instanceof ApiError ? error.message : "アサイン作成に失敗しました");
    },
  });

  const updateMutation = useMutation({
    mutationFn: () => {
      if (!editingAssignment) {
        throw new Error("対象アサインを選択してください");
      }
      return updateAssignment(editingAssignment.id, {
        shift_slot_id: editShiftSlotId,
        worker_id: editWorkerId,
        role_id: editRoleId,
        locked_price_sales: editLockedPriceSales || null,
        locked_price_outsource: editLockedPriceOutsource || null,
      });
    },
    onSuccess: async () => {
      setEditError("");
      setEditingAssignment(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["assignments"] }),
        queryClient.invalidateQueries({ queryKey: ["shift-slots"] }),
      ]);
    },
    onError: (error: unknown) => {
      setEditError(error instanceof ApiError ? error.message : "アサイン更新に失敗しました");
    },
  });

  const statusMutation = useMutation({
    mutationFn: () => {
      if (!selectedAssignment) {
        throw new Error("対象アサインを選択してください");
      }
      return updateAssignmentStatus(selectedAssignment.id, {
        status: nextStatus,
        cancel_reason: nextStatus === "canceled" ? cancelReason : null,
        reopen_reason: nextStatus !== "canceled" ? reopenReason : null,
      });
    },
    onSuccess: async () => {
      setActionError("");
      setSelectedAssignment(null);
      setCancelReason("");
      setReopenReason("");
      await Promise.all([
        queryClient.refetchQueries({ queryKey: ["assignments"], type: "active" }),
        queryClient.refetchQueries({ queryKey: ["assignment-cancellation-history", periodKey], type: "active" }),
      ]);
    },
    onError: (error: unknown) => {
      setActionError(error instanceof ApiError ? error.message : "アサイン状態更新に失敗しました");
    },
  });

  const assignmentHistoryQuery = useQuery({
    queryKey: ["assignment-history", selectedAssignment?.id],
    enabled: Boolean(selectedAssignment?.id),
    queryFn: () =>
      searchAuditLogs({
        target_type: "assignment",
        target_id: selectedAssignment?.id,
        offset: 0,
        limit: 10,
      }),
  });

  const cancellationHistoryQuery = useQuery({
    queryKey: ["assignment-cancellation-history", periodKey],
    queryFn: () =>
      getAssignmentCancellationHistory({
        work_date_from: workDateFrom,
        work_date_to: workDateTo,
        offset: 0,
        limit: 10,
      }),
  });

  const selectionSetsQuery = useQuery({
    queryKey: ["assignment-selection-sets", periodKey],
    queryFn: () => getAssignmentSelectionSets({ period_key: periodKey }),
  });

  const bulkStatusMutation = useMutation({
    mutationFn: (assignmentIds: string[]) =>
      bulkUpdateAssignmentStatus({
        assignment_ids: assignmentIds,
        status: bulkNextStatus,
        cancel_reason: bulkNextStatus === "canceled" ? bulkCancelReason : null,
        reopen_reason: bulkNextStatus !== "canceled" ? bulkReopenReason : null,
      }),
    onSuccess: async () => {
      setBulkError("");
      setSelectedAssignmentRows({});
      setBulkCancelReason("");
      setBulkReopenReason("");
      setSelectedAssignment(null);
      setEditingAssignment(null);
      await Promise.all([
        queryClient.refetchQueries({ queryKey: ["assignments"], type: "active" }),
        queryClient.refetchQueries({ queryKey: ["assignment-cancellation-history", periodKey], type: "active" }),
      ]);
    },
    onError: (error: unknown) => {
      setBulkError(error instanceof ApiError ? error.message : "アサイン一括状態更新に失敗しました");
    },
  });

  const saveSelectionSetMutation = useMutation({
    mutationFn: () =>
      createAssignmentSelectionSet({
        name: selectionSetName.trim(),
        period_key: periodKey,
        assignment_ids: selectedAssignmentIds,
        is_shared: selectionSetShared,
      }),
    onSuccess: async () => {
      setSelectionSetName("");
      setSelectionSetShared(false);
      setSelectionSetError("");
      await queryClient.invalidateQueries({ queryKey: ["assignment-selection-sets", periodKey] });
    },
    onError: (error: unknown) => {
      setSelectionSetError(error instanceof ApiError ? error.message : "選択セットの保存に失敗しました");
    },
  });

  const deleteSelectionSetMutation = useMutation({
    mutationFn: (selectionSetId: string) => deleteAssignmentSelectionSet(selectionSetId),
    onSuccess: async () => {
      setSelectionSetError("");
      await queryClient.invalidateQueries({ queryKey: ["assignment-selection-sets", periodKey] });
    },
    onError: (error: unknown) => {
      setSelectionSetError(error instanceof ApiError ? error.message : "選択セットの削除に失敗しました");
    },
  });

  if (assignmentsQuery.isLoading) {
    return <LoadingOverlay label="アサイン一覧を読み込み中..." />;
  }

  if (assignmentsQuery.error instanceof ApiError && assignmentsQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (assignmentsQuery.isError || !assignmentsQuery.data) {
    return <ErrorState title="アサイン一覧の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  const currentRows = assignmentsQuery.data.items;
  const selectedAssignmentIds = Object.entries(selectedAssignmentRows)
    .filter(([, checked]) => checked)
    .map(([assignmentId]) => assignmentId);
  const currentPageSelectedCount = currentRows.filter((row) => selectedAssignmentRows[row.id]).length;
  const allRowsSelected = currentRows.length > 0 && currentPageSelectedCount === currentRows.length;

  const toggleAssignmentSelection = (assignmentId: string, checked: boolean) => {
    setSelectedAssignmentRows((current) => ({
      ...current,
      [assignmentId]: checked,
    }));
  };

  const toggleCurrentPageSelection = (checked: boolean) => {
    setSelectedAssignmentRows((current) => {
      const nextSelectedRows = { ...current };
      for (const row of currentRows) {
        nextSelectedRows[row.id] = checked;
      }
      return nextSelectedRows;
    });
  };

  const clearAllSelections = () => {
    setSelectedAssignmentRows({});
  };

  const saveCurrentSelectionSet = () => {
    const trimmedName = selectionSetName.trim();
    if (!trimmedName || selectedAssignmentIds.length === 0) {
      return;
    }
    saveSelectionSetMutation.mutate();
  };

  const restoreSelectionSet = (selectionSet: AssignmentSelectionSetItem) => {
    const nextSelectedRows: Record<string, boolean> = {};
    for (const assignmentId of selectionSet.assignment_ids) {
      nextSelectedRows[assignmentId] = true;
    }
    setSelectedAssignmentRows(nextSelectedRows);
    setBulkError("");
    setSelectionSetError("");
  };

  const deleteSelectionSet = (selectionSetId: string) => {
    deleteSelectionSetMutation.mutate(selectionSetId);
  };

  const submitBulkStatusUpdate = () => {
    if (selectedAssignmentIds.length === 0) {
      return;
    }

    const previewLabels = currentRows
      .filter((row) => selectedAssignmentRows[row.id])
      .slice(0, 3)
      .map((row) => `${row.worker_name} / ${row.project_name}`);
    const remainingCount = selectedAssignmentIds.length - previewLabels.length;
    const suffix = remainingCount > 0 ? ` ほか${remainingCount}件` : "";
    const targetLabel = bulkNextStatus === "tentative" ? "仮確定" : bulkNextStatus === "confirmed" ? "確定" : "取消";
    const previewText = previewLabels.length > 0 ? previewLabels.join("、") : "他ページで選択されたアサイン";
    const confirmationMessage = `選択中 ${selectedAssignmentIds.length} 件を ${targetLabel} に更新します。対象: ${previewText}${suffix}`;

    if (!window.confirm(confirmationMessage)) {
      return;
    }

    bulkStatusMutation.mutate(selectedAssignmentIds);
  };

  return (
    <div className="page-stack">
      <PageHeader title="アサイン一覧" description="予定、役割、ロック単価を一覧で確認し、作成・編集・単件/一括の状態変更を行います。" />

      <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
        <strong>アサインを作成</strong>
        <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
          <label>
            案件
            <select value={createProjectId} onChange={(event) => setCreateProjectId(event.target.value)}>
              <option value="">選択してください</option>
              {(projectsQuery.data?.items ?? []).map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            シフト枠
            <select value={createShiftSlotId} onChange={(event) => setCreateShiftSlotId(event.target.value)}>
              <option value="">選択してください</option>
              {(shiftSlotsQuery.data?.items ?? []).map((row) => (
                <option key={row.id} value={row.id}>{`${row.project_name} / ${formatDate(row.work_date)} / ${row.shift_label || "シフト未設定"}`}</option>
              ))}
            </select>
          </label>
          <label>
            稼働者
            <select value={createWorkerId} onChange={(event) => setCreateWorkerId(event.target.value)}>
              <option value="">選択してください</option>
              {(workersQuery.data?.items ?? []).map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            役割
            <select value={createRoleId} onChange={(event) => setCreateRoleId(event.target.value)}>
              <option value="">選択してください</option>
              {(rolesQuery.data?.items ?? []).map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            初期状態
            <select value={createStatus} onChange={(event) => setCreateStatus(event.target.value as "tentative" | "confirmed")}>
              <option value="tentative">仮確定</option>
              <option value="confirmed">確定</option>
            </select>
          </label>
          <label>
            売上単価
            <input value={createLockedPriceSales} onChange={(event) => setCreateLockedPriceSales(event.target.value)} placeholder="任意" />
          </label>
          <label>
            外注単価
            <input value={createLockedPriceOutsource} onChange={(event) => setCreateLockedPriceOutsource(event.target.value)} placeholder="任意" />
          </label>
        </div>
        {formError ? <p className="form-error">{formError}</p> : null}
        <div>
          <button
            type="button"
            className="primary-button"
            onClick={() => createMutation.mutate()}
            disabled={!createShiftSlotId || !createWorkerId || !createRoleId || createMutation.isPending}
          >
            {createMutation.isPending ? "作成中..." : "アサインを作成"}
          </button>
        </div>
      </section>

      <FilterBar>
        <label>
          対象月
          <input type="month" value={monthValue} onChange={(event) => { setMonthValue(event.target.value); setPage(0); }} />
        </label>
        <label>
          ステータス
          <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(0); }}>
            <option value="">すべて</option>
            <option value="tentative">仮確定</option>
            <option value="confirmed">確定</option>
            <option value="canceled">取消</option>
          </select>
        </label>
      </FilterBar>

      <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
          <strong>一括状態更新</strong>
          <span>選択中 {selectedAssignmentIds.length} 件 / このページ {currentPageSelectedCount} 件 / 対象月 {periodKey}</span>
        </div>
        <p style={{ margin: 0, color: "var(--color-text-subtle, #667085)" }}>選択は対象月内でページ・ステータス切替をまたいで保持されます。保存済みセットを読み込んで再利用することもできます。</p>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <button type="button" onClick={() => toggleCurrentPageSelection(true)} disabled={currentRows.length === 0}>このページを全選択</button>
          <button type="button" onClick={() => toggleCurrentPageSelection(false)} disabled={currentPageSelectedCount === 0}>このページを解除</button>
          <button type="button" onClick={clearAllSelections} disabled={selectedAssignmentIds.length === 0}>すべて解除</button>
        </div>
        <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "minmax(220px, 2fr) auto" }}>
          <label>
            保存セット名
            <input value={selectionSetName} onChange={(event) => setSelectionSetName(event.target.value)} placeholder="例: 4月前半の確定候補" />
          </label>
          <div style={{ alignSelf: "end" }}>
            <button type="button" onClick={saveCurrentSelectionSet} disabled={!selectionSetName.trim() || selectedAssignmentIds.length === 0 || saveSelectionSetMutation.isPending}>現在の選択を保存</button>
          </div>
        </div>
        <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <input type="checkbox" checked={selectionSetShared} onChange={(event) => setSelectionSetShared(event.target.checked)} disabled={!canShareSelectionSet} />
          他ユーザーと共有する
        </label>
        {!canShareSelectionSet ? <p style={{ margin: 0, color: "var(--color-text-subtle, #667085)" }}>共有選択セットの保存は admin / ops のみ対応です。</p> : null}
        {selectionSetError ? <p className="form-error">{selectionSetError}</p> : null}
        {selectionSetsQuery.isLoading ? <p style={{ margin: 0 }}>保存済み選択セットを読み込み中...</p> : null}
        {selectionSetsQuery.isError ? <p className="form-error">保存済み選択セットの取得に失敗しました</p> : null}
        {!selectionSetsQuery.isLoading && !selectionSetsQuery.isError && (selectionSetsQuery.data?.items.length ?? 0) > 0 ? (
          <div style={{ display: "grid", gap: "0.5rem" }}>
            <strong>保存済み選択セット</strong>
            {(selectionSetsQuery.data?.items ?? []).map((selectionSet) => (
              <div key={selectionSet.id} style={{ border: "1px solid var(--color-border-subtle, #d0d5dd)", borderRadius: "0.75rem", padding: "0.75rem", display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
                <div style={{ display: "grid", gap: "0.2rem" }}>
                  <strong>{selectionSet.name}</strong>
                  <span>{selectionSet.available_assignment_count} / {selectionSet.total_assignment_count} 件 / 保存日時 {formatDateTime(selectionSet.created_at)}</span>
                  <span>{selectionSet.is_shared ? "共有" : "個人"} / 保存者 {selectionSet.created_by || "-"}</span>
                </div>
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  <button type="button" onClick={() => restoreSelectionSet(selectionSet)}>読み込む</button>
                  {selectionSet.editable ? <button type="button" onClick={() => deleteSelectionSet(selectionSet.id)} disabled={deleteSelectionSetMutation.isPending}>削除</button> : null}
                </div>
              </div>
            ))}
          </div>
        ) : null}
        <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
          <label>
            変更先状態
            <select value={bulkNextStatus} onChange={(event) => setBulkNextStatus(event.target.value as "tentative" | "confirmed" | "canceled")}>
              <option value="tentative">仮確定</option>
              <option value="confirmed">確定</option>
              <option value="canceled">取消</option>
            </select>
          </label>
        </div>
        {bulkNextStatus === "canceled" ? (
          <label>
            取消理由
            <textarea value={bulkCancelReason} onChange={(event) => setBulkCancelReason(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} />
          </label>
        ) : null}
        {bulkNextStatus !== "canceled" ? (
          <label>
            復帰理由
            <textarea value={bulkReopenReason} onChange={(event) => setBulkReopenReason(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} placeholder="取消中のアサインを含む場合は必須" />
          </label>
        ) : null}
        {bulkError ? <p className="form-error">{bulkError}</p> : null}
        <div>
          <button
            type="button"
            className="primary-button"
            onClick={submitBulkStatusUpdate}
            disabled={selectedAssignmentIds.length === 0 || bulkStatusMutation.isPending || (bulkNextStatus === "canceled" && !bulkCancelReason.trim())}
          >
            {bulkStatusMutation.isPending ? "一括更新中..." : "選択中アサインを更新"}
          </button>
        </div>
      </section>

      <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
          <strong>取消履歴</strong>
          <span>{periodKey} の最新 {Math.min(cancellationHistoryQuery.data?.items.length ?? 0, 10)} 件</span>
        </div>
        {cancellationHistoryQuery.isLoading ? <p style={{ margin: 0 }}>取消履歴を読み込み中...</p> : null}
        {cancellationHistoryQuery.isError ? <p className="form-error">取消履歴の取得に失敗しました</p> : null}
        {!cancellationHistoryQuery.isLoading && !cancellationHistoryQuery.isError && (cancellationHistoryQuery.data?.items.length ?? 0) === 0 ? (
          <p style={{ margin: 0, color: "var(--color-text-subtle, #667085)" }}>この期間の取消履歴はありません。</p>
        ) : null}
        {!cancellationHistoryQuery.isLoading && !cancellationHistoryQuery.isError && (cancellationHistoryQuery.data?.items.length ?? 0) > 0 ? (
          <DataTable
            columns={[
              { key: "canceled_at", header: "取消日時", render: (row) => formatDateTime(row.canceled_at) },
              { key: "project", header: "案件", render: (row) => row.project_name },
              { key: "worker", header: "稼働者", render: (row) => row.worker_name },
              { key: "shift", header: "シフト", render: (row) => row.shift_label || formatDate(row.work_date) },
              { key: "reason", header: "取消理由", render: (row) => row.cancel_reason || "-" },
              {
                key: "reopen",
                header: "復帰情報",
                render: (row) => row.reopened_at ? `${formatDateTime(row.reopened_at)} / ${row.reopened_by || "-"} / ${row.reopen_reason || "-"}` : "-",
              },
              { key: "current_status", header: "現在状態", render: (row) => <StatusBadge value={row.current_status} /> },
              {
                key: "actions",
                header: "操作",
                render: (row) => (
                  row.current_status === "canceled" ? (
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedAssignment({
                          id: row.assignment_id,
                          shift_slot_id: "",
                          project_id: row.project_id,
                          project_name: row.project_name,
                          work_date: row.work_date,
                          shift_label: row.shift_label,
                          worker_id: row.worker_id,
                          worker_name: row.worker_name,
                          worker_email: null,
                          role_id: row.role_id,
                          role_name: row.role_name,
                          status: row.current_status,
                          cancel_reason: row.cancel_reason,
                          worker_response_status: null,
                          worker_response_requested_at: null,
                          worker_response_at: null,
                          worker_response_note: null,
                          monitoring_status: null,
                          monitoring_reasons: [],
                          hours_since_response_request: null,
                          days_until_work: null,
                          locked_price_sales: null,
                          locked_price_outsource: null,
                        });
                        setNextStatus("tentative");
                        setCancelReason(row.cancel_reason || "");
                        setReopenReason(row.reopen_reason || "");
                        setActionError("");
                        setEditingAssignment(null);
                        setEditError("");
                      }}
                    >
                      再開
                    </button>
                  ) : (
                    <span style={{ color: "var(--color-text-subtle, #667085)" }}>再開済み</span>
                  )
                ),
              },
            ]}
            rows={cancellationHistoryQuery.data?.items ?? []}
            getRowKey={(row) => row.audit_log_id}
            emptyTitle="取消履歴はありません"
            emptyDescription="条件に一致する取消履歴は見つかりませんでした。"
          />
        ) : null}
      </section>

      {actionError ? <p style={{ margin: 0, color: "var(--color-danger, #b42318)" }}>{actionError}</p> : null}

      <DataTable
        columns={[
          {
            key: "select",
            header: (
              <input
                type="checkbox"
                aria-label="このページのアサインを全選択"
                checked={allRowsSelected}
                onChange={(event) => toggleCurrentPageSelection(event.target.checked)}
              />
            ),
            render: (row) => (
              <input
                type="checkbox"
                aria-label={`${row.worker_name} / ${row.project_name} を選択`}
                checked={Boolean(selectedAssignmentRows[row.id])}
                onChange={(event) => toggleAssignmentSelection(row.id, event.target.checked)}
              />
            ),
          },
          { key: "date", header: "日付", render: (row) => formatDate(row.work_date) },
          { key: "project", header: "案件", render: (row) => row.project_name },
          { key: "shift", header: "シフト", render: (row) => row.shift_label || "-" },
          { key: "worker", header: "稼働者", render: (row) => row.worker_name },
          { key: "role", header: "役割", render: (row) => row.role_name },
          { key: "status", header: "状態", render: (row) => <StatusBadge value={row.status} /> },
          { key: "reason", header: "取消理由", render: (row) => row.cancel_reason || "-" },
          { key: "sales", header: "売上単価", render: (row) => formatCurrency(row.locked_price_sales) },
          { key: "outsource", header: "外注単価", render: (row) => formatCurrency(row.locked_price_outsource) },
          {
            key: "actions",
            header: "操作",
            render: (row) => (
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                <button
                  onClick={() => {
                    setEditingAssignment(row);
                    setEditShiftSlotId(row.shift_slot_id);
                    setEditWorkerId(row.worker_id);
                    setEditRoleId(row.role_id);
                    setEditLockedPriceSales(row.locked_price_sales || "");
                    setEditLockedPriceOutsource(row.locked_price_outsource || "");
                    setEditError("");
                    setSelectedAssignment(null);
                    setCancelReason("");
                    setActionError("");
                  }}
                  style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}
                >
                  編集
                </button>
                <button
                  onClick={() => {
                    setSelectedAssignment(row);
                    setNextStatus(row.status === "confirmed" ? "tentative" : row.status === "canceled" ? "tentative" : "confirmed");
                    setCancelReason(row.cancel_reason || "");
                    setReopenReason("");
                    setActionError("");
                    setEditingAssignment(null);
                    setEditError("");
                  }}
                  style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}
                >
                  {row.status === "canceled" ? "再開" : "状態変更"}
                </button>
              </div>
            ),
          },
        ]}
        rows={assignmentsQuery.data.items}
        getRowKey={(row) => row.id}
        emptyTitle="アサインはありません"
        emptyDescription="条件に一致するアサインデータは見つかりませんでした。"
      />

      {editingAssignment ? (
        <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
          <strong>編集: {editingAssignment.worker_name} / {editingAssignment.project_name}</strong>
          <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
            <label>
              シフト枠
              <select value={editShiftSlotId} onChange={(event) => setEditShiftSlotId(event.target.value)}>
                <option value="">選択してください</option>
                {(editShiftSlotsQuery.data?.items ?? []).map((row) => (
                  <option key={row.id} value={row.id}>{`${row.project_name} / ${formatDate(row.work_date)} / ${row.shift_label || "シフト未設定"}`}</option>
                ))}
              </select>
            </label>
            <label>
              稼働者
              <select value={editWorkerId} onChange={(event) => setEditWorkerId(event.target.value)}>
                <option value="">選択してください</option>
                {(workersQuery.data?.items ?? []).map((row) => (
                  <option key={row.id} value={row.id}>{row.name}</option>
                ))}
              </select>
            </label>
            <label>
              役割
              <select value={editRoleId} onChange={(event) => setEditRoleId(event.target.value)}>
                <option value="">選択してください</option>
                {(rolesQuery.data?.items ?? []).map((row) => (
                  <option key={row.id} value={row.id}>{row.name}</option>
                ))}
              </select>
            </label>
            <label>
              売上単価
              <input value={editLockedPriceSales} onChange={(event) => setEditLockedPriceSales(event.target.value)} placeholder="任意" />
            </label>
            <label>
              外注単価
              <input value={editLockedPriceOutsource} onChange={(event) => setEditLockedPriceOutsource(event.target.value)} placeholder="任意" />
            </label>
          </div>
          {editError ? <p className="form-error">{editError}</p> : null}
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <button
              type="button"
              className="primary-button"
              onClick={() => updateMutation.mutate()}
              disabled={!editShiftSlotId || !editWorkerId || !editRoleId || updateMutation.isPending}
            >
              {updateMutation.isPending ? "更新中..." : "アサインを更新"}
            </button>
            <button
              type="button"
              onClick={() => {
                setEditingAssignment(null);
                setEditError("");
              }}
            >
              キャンセル
            </button>
          </div>
        </section>
      ) : null}

      {selectedAssignment ? (
        <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
          <strong>{selectedAssignment.status === "canceled" ? "再開 / 状態変更" : "状態変更"}: {selectedAssignment.worker_name} / {selectedAssignment.project_name}</strong>
          <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
            <label>
              変更先状態
              <select value={nextStatus} onChange={(event) => setNextStatus(event.target.value as "tentative" | "confirmed" | "canceled")}>
                <option value="tentative">仮確定</option>
                <option value="confirmed">確定</option>
                <option value="canceled">取消</option>
              </select>
            </label>
          </div>
          {nextStatus === "canceled" ? (
            <label>
              取消理由
              <textarea value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} />
            </label>
          ) : null}
          {selectedAssignment.status === "canceled" && nextStatus !== "canceled" ? (
            <label>
              復帰理由
              <textarea value={reopenReason} onChange={(event) => setReopenReason(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} />
            </label>
          ) : null}
          <div style={{ display: "grid", gap: "0.5rem" }}>
            <strong>変更履歴</strong>
            {assignmentHistoryQuery.isLoading ? <p style={{ margin: 0 }}>履歴を読み込み中...</p> : null}
            {assignmentHistoryQuery.error instanceof ApiError && assignmentHistoryQuery.error.status === 403 ? (
              <p style={{ margin: 0, color: "var(--color-text-subtle, #667085)" }}>監査ログ参照権限がないため履歴を表示できません。</p>
            ) : null}
            {assignmentHistoryQuery.isError && !(assignmentHistoryQuery.error instanceof ApiError && assignmentHistoryQuery.error.status === 403) ? (
              <p style={{ margin: 0, color: "var(--color-danger, #b42318)" }}>履歴の取得に失敗しました。</p>
            ) : null}
            {!assignmentHistoryQuery.isLoading && !assignmentHistoryQuery.isError && (assignmentHistoryQuery.data?.items.length ?? 0) === 0 ? (
              <p style={{ margin: 0, color: "var(--color-text-subtle, #667085)" }}>履歴はまだありません。</p>
            ) : null}
            {!assignmentHistoryQuery.isLoading && !assignmentHistoryQuery.isError && (assignmentHistoryQuery.data?.items.length ?? 0) > 0 ? (
              <div style={{ display: "grid", gap: "0.5rem" }}>
                {(assignmentHistoryQuery.data?.items ?? []).map((log) => (
                  <div key={log.id} style={{ border: "1px solid var(--color-border-subtle, #d0d5dd)", borderRadius: "0.75rem", padding: "0.75rem", display: "grid", gap: "0.25rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" }}>
                      <strong>{formatAuditAction(log.action)}</strong>
                      <span>{formatDateTime(log.timestamp)}</span>
                    </div>
                    <span>実行者: {log.actor || "-"}</span>
                    <span>{formatAuditSummary(log.reason || log.details_summary || "-")}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <button
              type="button"
              className="primary-button"
              onClick={() => statusMutation.mutate()}
              disabled={statusMutation.isPending || (nextStatus === "canceled" && !cancelReason.trim()) || (selectedAssignment.status === "canceled" && nextStatus !== "canceled" && !reopenReason.trim())}
            >
              {statusMutation.isPending ? "更新中..." : selectedAssignment.status === "canceled" && nextStatus !== "canceled" ? "再開する" : "状態を更新"}
            </button>
            <button type="button" onClick={() => { setSelectedAssignment(null); setCancelReason(""); setReopenReason(""); setActionError(""); }}>
              キャンセル
            </button>
          </div>
        </section>
      ) : null}

      <PaginationBar
        page={page}
        total={assignmentsQuery.data.total}
        limit={assignmentsQuery.data.limit}
        onPrevious={() => setPage((value) => Math.max(0, value - 1))}
        onNext={() => setPage((value) => value + 1)}
      />
    </div>
  );
}