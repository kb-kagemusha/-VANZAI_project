import { Navigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { PaginationBar } from "../components/PaginationBar";
import { useAuth } from "../lib/auth/auth-context";
import {
  ApiError,
  createWorker,
  deleteWorker,
  getWorkerAvailabilityPreferences,
  getSuppliers,
  getWorkers,
  updateWorker,
} from "../lib/api/client";
import type { WorkerAvailabilityPreference, WorkerListItem } from "../types/api";

const PAGE_SIZE = 30;

const weekdayLabels = ["日曜", "月曜", "火曜", "水曜", "木曜", "金曜", "土曜"];

const availabilityPreferenceLabels: Record<string, string> = {
  available_all_day: "稼働OK（1日）",
  available_after_15: "稼働OK（15時〜）",
  unavailable: "稼働不可",
  consult_required: "事前相談",
};

function formatAvailabilityPreference(value: string | null | undefined) {
  if (!value) {
    return "自動設定なし";
  }

  return availabilityPreferenceLabels[value] || value;
}

function buildAvailabilityPreferenceSummary(preferences: WorkerAvailabilityPreference | undefined) {
  return weekdayLabels.map((label, index) => ({
    label,
    value: formatAvailabilityPreference(preferences?.weekly_default_statuses[String(index)]),
  }));
}

export function WorkersPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [isActive, setIsActive] = useState("");
  const [page, setPage] = useState(0);

  // 新規作成フォーム
  const [createName, setCreateName] = useState("");
  const [createEmail, setCreateEmail] = useState("");
  const [createPhone, setCreatePhone] = useState("");
  const [createSupplierId, setCreateSupplierId] = useState("");
  const [createNotes, setCreateNotes] = useState("");
  const [createIsActive, setCreateIsActive] = useState(true);
  const [formError, setFormError] = useState("");
  const [formMessage, setFormMessage] = useState("");

  // 編集フォーム
  const [selectedWorker, setSelectedWorker] = useState<WorkerListItem | null>(null);
  const [editName, setEditName] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editSupplierId, setEditSupplierId] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editIsActive, setEditIsActive] = useState(true);
  const [editError, setEditError] = useState("");
  const [editMessage, setEditMessage] = useState("");

  const workersQuery = useQuery({
    queryKey: ["workers-list", search, isActive, page],
    queryFn: () =>
      getWorkers({
        search: search || undefined,
        is_active: isActive === "" ? undefined : isActive === "true",
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        sort_by: "name",
        sort_order: "asc",
      }),
  });

  const supplierOptionsQuery = useQuery({
    queryKey: ["suppliers-master-options"],
    queryFn: () => getSuppliers({ limit: 200, sort_by: "name", sort_order: "asc", is_active: true }),
    enabled: user?.role === "admin",
  });

  const workerPreferencesQuery = useQuery({
    queryKey: ["worker-availability-preferences", selectedWorker?.id],
    queryFn: () => getWorkerAvailabilityPreferences(selectedWorker!.id),
    enabled: Boolean(selectedWorker),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createWorker({
        name: createName,
        email: createEmail || null,
        phone: createPhone || null,
        introducer_supplier_id: createSupplierId || null,
        notes: createNotes || null,
        is_active: createIsActive,
        smoking_area_ok: null,
        has_p_shirt: null,
        has_best: null,
        stores_training_done: null,
        pioneer_training_done: null,
      }),
    onSuccess: async () => {
      setFormError("");
      setFormMessage("稼働者を追加しました");
      setCreateName("");
      setCreateEmail("");
      setCreatePhone("");
      setCreateSupplierId("");
      setCreateNotes("");
      setCreateIsActive(true);
      setPage(0);
      await queryClient.invalidateQueries({ queryKey: ["workers-list"] });
    },
    onError: (error: unknown) => {
      setFormMessage("");
      setFormError(error instanceof ApiError ? error.message : "稼働者の追加に失敗しました");
    },
  });

  const updateMutation = useMutation({
    mutationFn: () => {
      if (!selectedWorker) throw new Error("対象稼働者を選択してください");
      return updateWorker(selectedWorker.id, {
        name: editName,
        email: editEmail || null,
        phone: editPhone || null,
        introducer_supplier_id: editSupplierId || null,
        notes: editNotes || null,
        is_active: editIsActive,
        smoking_area_ok: selectedWorker.smoking_area_ok ?? null,
        has_p_shirt: selectedWorker.has_p_shirt ?? null,
        has_best: selectedWorker.has_best ?? null,
        stores_training_done: selectedWorker.stores_training_done ?? null,
        pioneer_training_done: selectedWorker.pioneer_training_done ?? null,
      });
    },
    onSuccess: async () => {
      setEditError("");
      setEditMessage("更新しました");
      await queryClient.invalidateQueries({ queryKey: ["workers-list"] });
    },
    onError: (error: unknown) => {
      setEditMessage("");
      setEditError(error instanceof ApiError ? error.message : "更新に失敗しました");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (workerId: string) => deleteWorker(workerId),
    onSuccess: async () => {
      closeEditor();
      setPage(0);
      await queryClient.invalidateQueries({ queryKey: ["workers-list"] });
    },
    onError: (error: unknown) => {
      setEditError(error instanceof ApiError ? error.message : "削除に失敗しました");
    },
  });

  function handleDelete(worker: WorkerListItem) {
    if (!window.confirm(`「${worker.name}」を削除します。\nこの操作は元に戻せません（論理削除）。\n員を削除しますか？`)) return;
    deleteMutation.mutate(worker.id);
  }

  function openEditor(worker: WorkerListItem) {
    setSelectedWorker(worker);
    setEditName(worker.name);
    setEditEmail(worker.email ?? "");
    setEditPhone(worker.phone ?? "");
    setEditSupplierId(worker.introducer_supplier_id ?? "");
    setEditNotes(worker.notes ?? "");
    setEditIsActive(worker.is_active);
    setEditError("");
    setEditMessage("");
  }

  function closeEditor() {
    setSelectedWorker(null);
    setEditError("");
    setEditMessage("");
  }

  function handleSearch(q: string) {
    setSearch(q);
    setPage(0);
    closeEditor();
  }

  if (workersQuery.isLoading) {
    return <LoadingOverlay label="稼働者一覧を読み込み中..." />;
  }

  if (workersQuery.error instanceof ApiError && workersQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (workersQuery.isError || !workersQuery.data) {
    return <ErrorState title="稼働者一覧の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  const { items, total } = workersQuery.data;
  const supplierOptions = supplierOptionsQuery.data?.items ?? [];
  const preferenceSummaryItems = buildAvailabilityPreferenceSummary(workerPreferencesQuery.data);

  return (
    <div className="page-stack">
      <PageHeader
        title="稼働者一覧"
        description="登録された稼働者（スタッフ）の一覧です。"
        eyebrow="マスタ"
      />

      <FilterBar>
        <label>
          名前・メール検索
          <input
            type="search"
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="名前・メールで検索"
          />
        </label>
        <label>
          状態
          <select value={isActive} onChange={(e) => { setIsActive(e.target.value); setPage(0); }}>
            <option value="">すべて</option>
            <option value="true">有効</option>
            <option value="false">無効</option>
          </select>
        </label>
      </FilterBar>

      {/* 新規追加フォーム（admin のみ） */}
      {user?.role === "admin" ? (
        <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
          <strong>稼働者を追加</strong>
          <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
            <label>
              名前 <span style={{ color: "#dc2626" }}>*</span>
              <input
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                placeholder="氏名"
              />
            </label>
            <label>
              メール
              <input
                type="email"
                value={createEmail}
                onChange={(e) => setCreateEmail(e.target.value)}
                placeholder="任意"
              />
            </label>
            <label>
              電話
              <input
                value={createPhone}
                onChange={(e) => setCreatePhone(e.target.value)}
                placeholder="任意"
              />
            </label>
            <label>
              紹介会社
              <select value={createSupplierId} onChange={(e) => setCreateSupplierId(e.target.value)}>
                <option value="">未設定</option>
                {supplierOptions.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </label>
            <label>
              備考
              <input
                value={createNotes}
                onChange={(e) => setCreateNotes(e.target.value)}
                placeholder="任意"
              />
            </label>
            <label style={{ display: "flex", flexDirection: "column" }}>
              有効
              <input
                type="checkbox"
                checked={createIsActive}
                onChange={(e) => setCreateIsActive(e.target.checked)}
                style={{ marginTop: "0.5rem", width: "auto" }}
              />
            </label>
          </div>
          {formError ? <p className="form-error">{formError}</p> : null}
          {formMessage ? <p style={{ margin: 0, color: "#16a34a" }}>{formMessage}</p> : null}
          <div>
            <button
              type="button"
              onClick={() => createMutation.mutate()}
              disabled={!createName.trim() || createMutation.isPending}
            >
              {createMutation.isPending ? "追加中..." : "追加"}
            </button>
          </div>
        </section>
      ) : null}

      {/* 編集パネル（admin のみ・行クリックで表示） */}
      {user?.role === "admin" && selectedWorker ? (
        <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <strong>{selectedWorker.name} を編集</strong>
            <button type="button" onClick={closeEditor}>閉じる</button>
          </div>
          <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
            <label>
              名前
              <input value={editName} onChange={(e) => setEditName(e.target.value)} />
            </label>
            <label>
              メール
              <input type="email" value={editEmail} onChange={(e) => setEditEmail(e.target.value)} />
            </label>
            <label>
              電話
              <input value={editPhone} onChange={(e) => setEditPhone(e.target.value)} />
            </label>
            <label>
              紹介会社
              <select value={editSupplierId} onChange={(e) => setEditSupplierId(e.target.value)}>
                <option value="">未設定</option>
                {supplierOptions.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </label>
            <label>
              備考
              <input value={editNotes} onChange={(e) => setEditNotes(e.target.value)} />
            </label>
            <label style={{ display: "flex", flexDirection: "column" }}>
              有効
              <input
                type="checkbox"
                checked={editIsActive}
                onChange={(e) => setEditIsActive(e.target.checked)}
                style={{ marginTop: "0.5rem", width: "auto" }}
              />
            </label>
          </div>
          {editError ? <p className="form-error">{editError}</p> : null}
          {editMessage ? <p style={{ margin: 0, color: "#16a34a" }}>{editMessage}</p> : null}

          <section className="worker-preferences-card">
            <div className="worker-preferences-header">
              <div>
                <strong>基本スケジュール</strong>
                <p>スタッフモバイルの自動候補に使っている既定設定です。</p>
              </div>
              <span className={`status-badge ${workerPreferencesQuery.data?.auto_apply_enabled ? "active" : "inactive"}`}>
                {workerPreferencesQuery.data?.auto_apply_enabled ? "自動候補オン" : "自動候補オフ"}
              </span>
            </div>

            {workerPreferencesQuery.isLoading ? <p style={{ margin: 0, color: "#6b7280" }}>基本スケジュールを読み込み中...</p> : null}
            {workerPreferencesQuery.isError ? <p className="form-error">{workerPreferencesQuery.error instanceof ApiError ? workerPreferencesQuery.error.message : "基本スケジュールの取得に失敗しました"}</p> : null}

            {!workerPreferencesQuery.isLoading && !workerPreferencesQuery.isError ? (
              <>
                <div className="worker-preferences-grid">
                  {preferenceSummaryItems.map((item) => (
                    <div key={item.label} className="worker-preference-item">
                      <span className="worker-preference-label">{item.label}</span>
                      <strong>{item.value}</strong>
                    </div>
                  ))}
                </div>
                <div className="worker-preferences-footer">
                  <span>祝日: {formatAvailabilityPreference(workerPreferencesQuery.data?.holiday_default_status)}</span>
                  <span>更新日時: {workerPreferencesQuery.data?.updated_at ? new Date(workerPreferencesQuery.data.updated_at).toLocaleString("ja-JP") : "未保存"}</span>
                </div>
              </>
            ) : null}
          </section>

          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={() => updateMutation.mutate()}
              disabled={!editName.trim() || updateMutation.isPending || deleteMutation.isPending}
            >
              {updateMutation.isPending ? "更新中..." : "更新"}
            </button>
            <button
              type="button"
              onClick={() => handleDelete(selectedWorker)}
              disabled={updateMutation.isPending || deleteMutation.isPending}
              style={{ background: "rgba(220,38,38,0.1)", color: "#b91c1c", borderColor: "#fca5a5" }}
            >
              {deleteMutation.isPending ? "削除中..." : "削除"}
            </button>
          </div>
        </section>
      ) : null}

      <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
          <span style={{ fontSize: "0.875rem", color: "#6b7280" }}>
            {total} 件中 {page * PAGE_SIZE + 1}〜{Math.min((page + 1) * PAGE_SIZE, total)} 件を表示
          </span>
        </div>

        <DataTable
          columns={[
            {
              key: "name",
              header: "名前",
              render: (row) => (
                <span style={{ fontWeight: 500 }}>{row.name}</span>
              ),
            },
            {
              key: "email",
              header: "メール",
              render: (row) => row.email ?? <span style={{ color: "#9ca3af" }}>未設定</span>,
            },
            {
              key: "phone",
              header: "電話",
              render: (row) => row.phone ?? <span style={{ color: "#9ca3af" }}>—</span>,
            },
            {
              key: "supplier",
              header: "紹介会社",
              render: (row) => row.introducer_supplier_name ?? <span style={{ color: "#9ca3af" }}>—</span>,
            },
            {
              key: "is_active",
              header: "状態",
              render: (row) => (
                <span className={`status-badge ${row.is_active ? "active" : "inactive"}`}>
                  {row.is_active ? "有効" : "無効"}
                </span>
              ),
            },
            {
              key: "notes",
              header: "備考",
              render: (row) => row.notes
                ? <span style={{ maxWidth: "200px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block" }}>{row.notes}</span>
                : <span style={{ color: "#9ca3af" }}>—</span>,
            },
            ...(user?.role === "admin"
              ? [{
                  key: "edit" as const,
                  header: "",
                  render: (row: WorkerListItem) => (
                    <div style={{ display: "flex", gap: "0.375rem" }}>
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); openEditor(row); }}
                        style={{ fontSize: "0.8rem" }}
                      >
                        編集
                      </button>
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); handleDelete(row); }}
                        disabled={deleteMutation.isPending}
                        style={{ fontSize: "0.8rem", background: "rgba(220,38,38,0.1)", color: "#b91c1c", borderColor: "#fca5a5" }}
                      >
                        削除
                      </button>
                    </div>
                  ),
                }]
              : []),
          ]}
          rows={items}
          getRowKey={(row) => row.id}
          emptyTitle="稼働者が見つかりません"
          emptyDescription="条件を変えて検索するか、新規追加してください。"
        />
      </section>

      <PaginationBar
        page={page}
        total={total}
        limit={PAGE_SIZE}
        onPrevious={() => setPage((p) => Math.max(0, p - 1))}
        onNext={() => setPage((p) => p + 1)}
      />
    </div>
  );
}
