import { Navigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { PaginationBar } from "../components/PaginationBar";
import { StatusBadge } from "../components/StatusBadge";
import { ApiError, createShiftSlot, getProjects, getShiftSlots, updateShiftSlot } from "../lib/api/client";
import { currentMonthInput, formatDate, periodKeyToDateRange, toPeriodKey } from "../lib/formatters";
import type { ShiftSlotListItem } from "../types/api";

const PAGE_SIZE = 20;

function formatTimeRange(shiftSlot: ShiftSlotListItem) {
  if (!shiftSlot.start_time || !shiftSlot.end_time) {
    return "-";
  }

  return `${shiftSlot.start_time.slice(0, 5)} - ${shiftSlot.end_time.slice(0, 5)}`;
}

export function ShiftSlotsPage() {
  const [projectId, setProjectId] = useState("");
  const [monthValue, setMonthValue] = useState(currentMonthInput());
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("work_date");
  const [sortOrder, setSortOrder] = useState("desc");
  const [page, setPage] = useState(0);
  const [createProjectId, setCreateProjectId] = useState("");
  const [createWorkDate, setCreateWorkDate] = useState("");
  const [createStartTime, setCreateStartTime] = useState("09:00");
  const [createEndTime, setCreateEndTime] = useState("18:00");
  const [createShiftLabel, setCreateShiftLabel] = useState("");
  const [createRequiredCount, setCreateRequiredCount] = useState("1");
  const [createNotes, setCreateNotes] = useState("");
  const [formError, setFormError] = useState("");
  const [editingShiftSlot, setEditingShiftSlot] = useState<ShiftSlotListItem | null>(null);
  const [editProjectId, setEditProjectId] = useState("");
  const [editWorkDate, setEditWorkDate] = useState("");
  const [editStartTime, setEditStartTime] = useState("");
  const [editEndTime, setEditEndTime] = useState("");
  const [editShiftLabel, setEditShiftLabel] = useState("");
  const [editRequiredCount, setEditRequiredCount] = useState("1");
  const [editNotes, setEditNotes] = useState("");
  const [editError, setEditError] = useState("");
  const [editMessage, setEditMessage] = useState("");
  const periodKey = toPeriodKey(monthValue);
  const { from: workDateFrom, to: workDateTo } = periodKeyToDateRange(periodKey);
  const queryClient = useQueryClient();

  const projectOptionsQuery = useQuery({
    queryKey: ["projects-shift-form"],
    queryFn: () => getProjects({ limit: 200, sort_by: "name", sort_order: "asc", is_active: true }),
  });

  const shiftSlotsQuery = useQuery({
    queryKey: ["shift-slots", projectId, monthValue, search, sortBy, sortOrder, page],
    queryFn: () =>
      getShiftSlots({
        project_id: projectId || undefined,
        work_date_from: workDateFrom,
        work_date_to: workDateTo,
        search: search || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createShiftSlot({
        project_id: createProjectId,
        work_date: createWorkDate,
        start_time: createStartTime || null,
        end_time: createEndTime || null,
        shift_label: createShiftLabel || null,
        required_count: Number(createRequiredCount || 0),
        notes: createNotes || null,
      }),
    onSuccess: async () => {
      setFormError("");
      setCreateWorkDate("");
      setCreateStartTime("09:00");
      setCreateEndTime("18:00");
      setCreateShiftLabel("");
      setCreateRequiredCount("1");
      setCreateNotes("");
      setPage(0);
      await queryClient.invalidateQueries({ queryKey: ["shift-slots"] });
    },
    onError: (error: unknown) => {
      setFormError(error instanceof ApiError ? error.message : "シフト枠作成に失敗しました");
    },
  });

  const updateMutation = useMutation({
    mutationFn: () => {
      if (!editingShiftSlot) {
        throw new Error("対象シフト枠を選択してください");
      }

      return updateShiftSlot(editingShiftSlot.id, {
        project_id: editProjectId,
        work_date: editWorkDate,
        start_time: editStartTime || null,
        end_time: editEndTime || null,
        shift_label: editShiftLabel || null,
        required_count: Number(editRequiredCount || 0),
        notes: editNotes || null,
      });
    },
    onSuccess: async (shiftSlot) => {
      setEditError("");
      setEditMessage("シフト枠を更新しました");
      openShiftSlotEditor(shiftSlot);
      await queryClient.invalidateQueries({ queryKey: ["shift-slots"] });
    },
    onError: (error: unknown) => {
      setEditMessage("");
      setEditError(error instanceof ApiError ? error.message : "シフト枠更新に失敗しました");
    },
  });

  const openShiftSlotEditor = (shiftSlot: ShiftSlotListItem) => {
    setEditingShiftSlot(shiftSlot);
    setEditProjectId(shiftSlot.project_id);
    setEditWorkDate(shiftSlot.work_date);
    setEditStartTime(shiftSlot.start_time ? shiftSlot.start_time.slice(0, 5) : "");
    setEditEndTime(shiftSlot.end_time ? shiftSlot.end_time.slice(0, 5) : "");
    setEditShiftLabel(shiftSlot.shift_label || "");
    setEditRequiredCount(String(shiftSlot.required_count));
    setEditNotes(shiftSlot.notes || "");
    setEditError("");
    setEditMessage("");
  };

  const closeShiftSlotEditor = () => {
    setEditingShiftSlot(null);
    setEditError("");
    setEditMessage("");
  };

  if (shiftSlotsQuery.isLoading) {
    return <LoadingOverlay label="シフト枠を読み込み中..." />;
  }

  if (shiftSlotsQuery.error instanceof ApiError && shiftSlotsQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (shiftSlotsQuery.isError || !shiftSlotsQuery.data) {
    return <ErrorState title="シフト枠の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  return (
    <div className="page-stack">
      <PageHeader title="シフト枠" description="案件ごとの募集枠を作成し、時間帯、人数、メモを編集します。" />

      <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
        <strong>シフト枠を作成</strong>
        <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
          <label>
            案件
            <select value={createProjectId} onChange={(event) => setCreateProjectId(event.target.value)}>
              <option value="">選択してください</option>
              {(projectOptionsQuery.data?.items ?? []).map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            稼働日
            <input type="date" value={createWorkDate} onChange={(event) => setCreateWorkDate(event.target.value)} />
          </label>
          <label>
            開始時刻
            <input type="time" value={createStartTime} onChange={(event) => setCreateStartTime(event.target.value)} />
          </label>
          <label>
            終了時刻
            <input type="time" value={createEndTime} onChange={(event) => setCreateEndTime(event.target.value)} />
          </label>
          <label>
            シフトラベル
            <input value={createShiftLabel} onChange={(event) => setCreateShiftLabel(event.target.value)} placeholder="日勤、夜勤など" />
          </label>
          <label>
            必要人数
            <input type="number" min={1} value={createRequiredCount} onChange={(event) => setCreateRequiredCount(event.target.value)} />
          </label>
        </div>
        <label>
          メモ
          <textarea value={createNotes} onChange={(event) => setCreateNotes(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} />
        </label>
        {formError ? <p className="form-error">{formError}</p> : null}
        <div>
          <button
            type="button"
            className="primary-button"
            onClick={() => createMutation.mutate()}
            disabled={!createProjectId || !createWorkDate || !createRequiredCount || createMutation.isPending}
          >
            {createMutation.isPending ? "作成中..." : "シフト枠を作成"}
          </button>
        </div>
      </section>

      {editingShiftSlot ? (
        <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
            <div style={{ display: "grid", gap: "0.2rem" }}>
              <strong>シフト枠を編集</strong>
              <span style={{ color: "var(--color-text-subtle, #667085)", fontSize: "0.9rem" }}>
                {editingShiftSlot.project_name} / {formatDate(editingShiftSlot.work_date)} / {formatTimeRange(editingShiftSlot)}
              </span>
            </div>
            <button type="button" onClick={closeShiftSlotEditor} style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}>
              閉じる
            </button>
          </div>
          <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
            <label>
              案件
              <select value={editProjectId} onChange={(event) => setEditProjectId(event.target.value)}>
                <option value="">選択してください</option>
                {(projectOptionsQuery.data?.items ?? []).map((row) => (
                  <option key={row.id} value={row.id}>{row.name}</option>
                ))}
              </select>
            </label>
            <label>
              稼働日
              <input type="date" value={editWorkDate} onChange={(event) => setEditWorkDate(event.target.value)} />
            </label>
            <label>
              開始時刻
              <input type="time" value={editStartTime} onChange={(event) => setEditStartTime(event.target.value)} />
            </label>
            <label>
              終了時刻
              <input type="time" value={editEndTime} onChange={(event) => setEditEndTime(event.target.value)} />
            </label>
            <label>
              シフトラベル
              <input value={editShiftLabel} onChange={(event) => setEditShiftLabel(event.target.value)} />
            </label>
            <label>
              必要人数
              <input type="number" min={1} value={editRequiredCount} onChange={(event) => setEditRequiredCount(event.target.value)} />
            </label>
          </div>
          <label>
            メモ
            <textarea value={editNotes} onChange={(event) => setEditNotes(event.target.value)} rows={4} style={{ width: "100%", resize: "vertical" }} />
          </label>
          {editError ? <p className="form-error">{editError}</p> : null}
          {editMessage ? <p style={{ margin: 0, color: "var(--color-success, #067647)" }}>{editMessage}</p> : null}
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <button
              type="button"
              className="primary-button"
              onClick={() => updateMutation.mutate()}
              disabled={!editProjectId || !editWorkDate || !editRequiredCount || updateMutation.isPending}
            >
              {updateMutation.isPending ? "更新中..." : "更新する"}
            </button>
            <button type="button" onClick={() => openShiftSlotEditor(editingShiftSlot)} disabled={updateMutation.isPending}>
              元に戻す
            </button>
          </div>
        </section>
      ) : null}

      <FilterBar>
        <label>
          案件
          <select value={projectId} onChange={(event) => { setProjectId(event.target.value); setPage(0); }}>
            <option value="">すべて</option>
            {(projectOptionsQuery.data?.items ?? []).map((row) => (
              <option key={row.id} value={row.id}>{row.name}</option>
            ))}
          </select>
        </label>
        <label>
          対象月
          <input type="month" value={monthValue} onChange={(event) => { setMonthValue(event.target.value); setPage(0); }} />
        </label>
        <label>
          検索
          <input value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder="案件名、シフトラベル" />
        </label>
        <label>
          ソート
          <select value={sortBy} onChange={(event) => { setSortBy(event.target.value); setPage(0); }}>
            <option value="work_date">稼働日</option>
            <option value="project_name">案件</option>
            <option value="shift_label">シフトラベル</option>
            <option value="required_count">必要人数</option>
          </select>
        </label>
        <label>
          順序
          <select value={sortOrder} onChange={(event) => { setSortOrder(event.target.value); setPage(0); }}>
            <option value="asc">昇順</option>
            <option value="desc">降順</option>
          </select>
        </label>
      </FilterBar>

      <DataTable
        columns={[
          { key: "project", header: "案件", render: (row) => row.project_name },
          { key: "date", header: "稼働日", render: (row) => formatDate(row.work_date) },
          { key: "time", header: "時間", render: (row) => formatTimeRange(row) },
          { key: "label", header: "シフトラベル", render: (row) => row.shift_label || "-" },
          { key: "required", header: "必要人数", render: (row) => row.required_count },
          { key: "assigned", header: "割当済", render: (row) => row.assigned_count },
          { key: "notes", header: "メモ", render: (row) => row.notes || "-" },
          {
            key: "status",
            header: "状態",
            render: (row) => (
              <StatusBadge value={row.assigned_count >= row.required_count ? "active" : "pending"} />
            ),
          },
          {
            key: "actions",
            header: "操作",
            render: (row) => (
              <button
                type="button"
                onClick={() => openShiftSlotEditor(row)}
                style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}
              >
                編集
              </button>
            ),
          },
        ]}
        rows={shiftSlotsQuery.data.items}
        getRowKey={(row) => row.id}
        emptyTitle="シフト枠はありません"
        emptyDescription="条件に一致するシフト枠は見つかりませんでした。"
      />

      <PaginationBar
        page={page}
        total={shiftSlotsQuery.data.total}
        limit={shiftSlotsQuery.data.limit}
        onPrevious={() => setPage((value) => Math.max(0, value - 1))}
        onNext={() => setPage((value) => value + 1)}
      />
    </div>
  );
}