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
  createWorkerBankAccount,
  deleteWorker,
  getWorkerAvailabilityPreferences,
  getWorkerBankAccounts,
  getSuppliers,
  getWorkers,
  updateWorkerBankAccount,
  updateWorker,
} from "../lib/api/client";
import { formatDate, formatMaskedAccountNumber } from "../lib/formatters";
import type { WorkerAvailabilityPreference, WorkerBankAccountItem, WorkerListItem } from "../types/api";

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

function validateEffectiveRange(effectiveFrom: string, effectiveUntil: string): void {
  if (effectiveUntil && effectiveUntil < effectiveFrom) {
    throw new ApiError(400, "有効終了日は有効開始日以降を指定してください");
  }
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

  // 口座フォーム
  const [bankBankName, setBankBankName] = useState("");
  const [bankBranchName, setBankBranchName] = useState("");
  const [bankBranchCode, setBankBranchCode] = useState("");
  const [bankAccountType, setBankAccountType] = useState("普通");
  const [bankAccountNumber, setBankAccountNumber] = useState("");
  const [bankHolderKana, setBankHolderKana] = useState("");
  const [bankEffectiveFrom, setBankEffectiveFrom] = useState("");
  const [bankEffectiveUntil, setBankEffectiveUntil] = useState("");
  const [bankIsPrimary, setBankIsPrimary] = useState(false);
  const [bankFormError, setBankFormError] = useState("");
  const [bankFormMessage, setBankFormMessage] = useState("");
  const [selectedBankAccount, setSelectedBankAccount] = useState<WorkerBankAccountItem | null>(null);
  const [editBankName, setEditBankName] = useState("");
  const [editBranchName, setEditBranchName] = useState("");
  const [editBranchCode, setEditBranchCode] = useState("");
  const [editBankAccountType, setEditBankAccountType] = useState("普通");
  const [editBankAccountNumber, setEditBankAccountNumber] = useState("");
  const [editBankHolderKana, setEditBankHolderKana] = useState("");
  const [editBankEffectiveFrom, setEditBankEffectiveFrom] = useState("");
  const [editBankEffectiveUntil, setEditBankEffectiveUntil] = useState("");
  const [editBankIsPrimary, setEditBankIsPrimary] = useState(false);
  const [bankEditError, setBankEditError] = useState("");
  const [bankEditMessage, setBankEditMessage] = useState("");

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

  const workerBankAccountsQuery = useQuery({
    queryKey: ["worker-bank-accounts", selectedWorker?.id],
    queryFn: () => getWorkerBankAccounts(selectedWorker!.id),
    enabled: Boolean(selectedWorker),
  });

  const createBankAccountMutation = useMutation({
    mutationFn: () => {
      if (!selectedWorker) throw new Error("稼働者を選択してください");
      validateEffectiveRange(bankEffectiveFrom, bankEffectiveUntil);
      return createWorkerBankAccount(selectedWorker.id, {
        bank_name: bankBankName,
        branch_name: bankBranchName,
        branch_code: bankBranchCode || null,
        account_type: bankAccountType,
        account_number: bankAccountNumber,
        account_holder_kana: bankHolderKana,
        transfer_destination_name: null,
        effective_from: bankEffectiveFrom,
        effective_until: bankEffectiveUntil || null,
        is_primary: bankIsPrimary,
      });
    },
    onSuccess: async () => {
      setBankFormError("");
      setBankFormMessage("口座を登録しました");
      setBankBankName(""); setBankBranchName(""); setBankBranchCode("");
      setBankAccountNumber(""); setBankHolderKana(""); setBankEffectiveFrom(""); setBankEffectiveUntil("");
      setBankIsPrimary(false);
      await queryClient.invalidateQueries({ queryKey: ["worker-bank-accounts", selectedWorker?.id] });
    },
    onError: (error: unknown) => {
      setBankFormMessage("");
      setBankFormError(error instanceof ApiError ? error.message : "口座登録に失敗しました");
    },
  });

  const updateBankAccountMutation = useMutation({
    mutationFn: () => {
      if (!selectedWorker || !selectedBankAccount) {
        throw new Error("更新対象の口座を選択してください");
      }
      validateEffectiveRange(editBankEffectiveFrom, editBankEffectiveUntil);
      return updateWorkerBankAccount(selectedWorker.id, selectedBankAccount.id, {
        bank_name: editBankName,
        branch_name: editBranchName,
        branch_code: editBranchCode || null,
        account_type: editBankAccountType,
        account_number: editBankAccountNumber,
        account_holder_kana: editBankHolderKana,
        transfer_destination_name: null,
        effective_from: editBankEffectiveFrom,
        effective_until: editBankEffectiveUntil || null,
        is_primary: editBankIsPrimary,
      });
    },
    onSuccess: async () => {
      setBankEditError("");
      setBankEditMessage("口座を更新しました");
      await queryClient.invalidateQueries({ queryKey: ["worker-bank-accounts", selectedWorker?.id] });
    },
    onError: (error: unknown) => {
      setBankEditMessage("");
      setBankEditError(error instanceof ApiError ? error.message : "口座更新に失敗しました");
    },
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createWorker({
        name: createName,
        furigana: null,
        email: createEmail || null,
        phone: createPhone || null,
        sole_proprietor_name: null,
        emergency_contact_name_kana: null,
        emergency_contact_phone: null,
        gender: null,
        invoice_registration_status: null,
        invoice_number: null,
        introducer_supplier_id: createSupplierId || null,
        notes: createNotes || null,
        is_active: createIsActive,
        smoking_area_ok: null,
        has_p_shirt: null,
        has_best: null,
        stores_training_done: null,
        pioneer_training_done: null,
        p_shirt_count: null,
        license_type: null,
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
        furigana: selectedWorker.furigana ?? null,
        email: editEmail || null,
        phone: editPhone || null,
        sole_proprietor_name: selectedWorker.sole_proprietor_name ?? null,
        emergency_contact_name_kana: selectedWorker.emergency_contact_name_kana ?? null,
        emergency_contact_phone: selectedWorker.emergency_contact_phone ?? null,
        gender: selectedWorker.gender ?? null,
        invoice_registration_status: selectedWorker.invoice_registration_status ?? null,
        invoice_number: selectedWorker.invoice_number ?? null,
        introducer_supplier_id: editSupplierId || null,
        notes: editNotes || null,
        is_active: editIsActive,
        smoking_area_ok: selectedWorker.smoking_area_ok ?? null,
        has_p_shirt: selectedWorker.has_p_shirt ?? null,
        has_best: selectedWorker.has_best ?? null,
        stores_training_done: selectedWorker.stores_training_done ?? null,
        pioneer_training_done: selectedWorker.pioneer_training_done ?? null,
        p_shirt_count: selectedWorker.p_shirt_count ?? null,
        license_type: selectedWorker.license_type ?? null,
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
    setSelectedBankAccount(null);
    setBankEditError("");
    setBankEditMessage("");
  }

  function closeEditor() {
    setSelectedWorker(null);
    setEditError("");
    setEditMessage("");
    setSelectedBankAccount(null);
    setBankEditError("");
    setBankEditMessage("");
  }

  function openBankEditor(account: WorkerBankAccountItem) {
    setSelectedBankAccount(account);
    setEditBankName(account.bank_name);
    setEditBranchName(account.branch_name);
    setEditBranchCode(account.branch_code ?? "");
    setEditBankAccountType(account.account_type);
    setEditBankAccountNumber(account.account_number);
    setEditBankHolderKana(account.account_holder_kana);
    setEditBankEffectiveFrom(account.effective_from);
    setEditBankEffectiveUntil(account.effective_until ?? "");
    setEditBankIsPrimary(account.is_primary);
    setBankEditError("");
    setBankEditMessage("");
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

          {/* 口座情報セクション */}
          <div style={{ borderTop: "1px solid #e5e7eb", paddingTop: "0.75rem", marginTop: "0.5rem" }}>
            <strong style={{ fontSize: "0.9rem" }}>振込先口座</strong>
            {workerBankAccountsQuery.isLoading ? <p style={{ margin: "0.5rem 0", color: "#6b7280", fontSize: "0.875rem" }}>読み込み中...</p> : null}
            {workerBankAccountsQuery.data?.items && workerBankAccountsQuery.data.items.length > 0 ? (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem", marginTop: "0.5rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #e5e7eb", textAlign: "left" }}>
                    <th style={{ padding: "0.25rem 0.5rem" }}>銀行</th>
                    <th style={{ padding: "0.25rem 0.5rem" }}>支店</th>
                    <th style={{ padding: "0.25rem 0.5rem" }}>種別</th>
                    <th style={{ padding: "0.25rem 0.5rem" }}>口座番号</th>
                    <th style={{ padding: "0.25rem 0.5rem" }}>口座名義(カナ)</th>
                    <th style={{ padding: "0.25rem 0.5rem" }}>有効開始</th>
                    <th style={{ padding: "0.25rem 0.5rem" }}>有効終了</th>
                    <th style={{ padding: "0.25rem 0.5rem" }}>主</th>
                    <th style={{ padding: "0.25rem 0.5rem" }}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {workerBankAccountsQuery.data.items.map((acc: WorkerBankAccountItem) => (
                    <tr key={acc.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                      <td style={{ padding: "0.25rem 0.5rem" }}>{acc.bank_name}</td>
                      <td style={{ padding: "0.25rem 0.5rem" }}>{acc.branch_name}</td>
                      <td style={{ padding: "0.25rem 0.5rem" }}>{acc.account_type}</td>
                      <td style={{ padding: "0.25rem 0.5rem" }}>{formatMaskedAccountNumber(acc.account_number)}</td>
                      <td style={{ padding: "0.25rem 0.5rem" }}>{acc.account_holder_kana}</td>
                      <td style={{ padding: "0.25rem 0.5rem" }}>{formatDate(acc.effective_from)}</td>
                      <td style={{ padding: "0.25rem 0.5rem" }}>{formatDate(acc.effective_until)}</td>
                      <td style={{ padding: "0.25rem 0.5rem" }}>{acc.is_primary ? "✓" : ""}</td>
                      <td style={{ padding: "0.25rem 0.5rem" }}>
                        <button type="button" style={{ fontSize: "0.8rem" }} onClick={() => openBankEditor(acc)}>編集</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              !workerBankAccountsQuery.isLoading ? <p style={{ margin: "0.5rem 0", color: "#9ca3af", fontSize: "0.875rem" }}>口座未登録</p> : null
            )}

            {selectedBankAccount ? (
              <section style={{ borderTop: "1px solid #e5e7eb", paddingTop: "0.75rem", marginTop: "0.75rem", display: "grid", gap: "0.5rem" }}>
                <strong style={{ fontSize: "0.85rem" }}>口座を編集</strong>
                <div style={{ display: "grid", gap: "0.5rem", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))" }}>
                  <label style={{ fontSize: "0.8rem" }}>
                    銀行名 *
                    <input value={editBankName} onChange={(e) => setEditBankName(e.target.value)} />
                  </label>
                  <label style={{ fontSize: "0.8rem" }}>
                    支店名 *
                    <input value={editBranchName} onChange={(e) => setEditBranchName(e.target.value)} />
                  </label>
                  <label style={{ fontSize: "0.8rem" }}>
                    支店コード
                    <input value={editBranchCode} onChange={(e) => setEditBranchCode(e.target.value)} maxLength={10} />
                  </label>
                  <label style={{ fontSize: "0.8rem" }}>
                    種別 *
                    <select value={editBankAccountType} onChange={(e) => setEditBankAccountType(e.target.value)}>
                      <option value="普通">普通</option>
                      <option value="当座">当座</option>
                      <option value="貯蓄">貯蓄</option>
                    </select>
                  </label>
                  <label style={{ fontSize: "0.8rem" }}>
                    口座番号 *
                    <input value={editBankAccountNumber} onChange={(e) => setEditBankAccountNumber(e.target.value)} maxLength={20} />
                  </label>
                  <label style={{ fontSize: "0.8rem" }}>
                    口座名義(カナ) *
                    <input value={editBankHolderKana} onChange={(e) => setEditBankHolderKana(e.target.value)} />
                  </label>
                  <label style={{ fontSize: "0.8rem" }}>
                    有効開始日 *
                    <input type="date" value={editBankEffectiveFrom} onChange={(e) => setEditBankEffectiveFrom(e.target.value)} />
                  </label>
                  <label style={{ fontSize: "0.8rem" }}>
                    有効終了日
                    <input type="date" value={editBankEffectiveUntil} onChange={(e) => setEditBankEffectiveUntil(e.target.value)} />
                  </label>
                  <label style={{ fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <input type="checkbox" checked={editBankIsPrimary} onChange={(e) => setEditBankIsPrimary(e.target.checked)} style={{ width: "auto" }} />
                    主口座
                  </label>
                </div>
                {bankEditError ? <p className="form-error" style={{ fontSize: "0.8rem" }}>{bankEditError}</p> : null}
                {bankEditMessage ? <p style={{ margin: 0, color: "#16a34a", fontSize: "0.8rem" }}>{bankEditMessage}</p> : null}
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  <button
                    type="button"
                    style={{ fontSize: "0.8rem" }}
                    onClick={() => updateBankAccountMutation.mutate()}
                    disabled={!editBankName.trim() || !editBranchName.trim() || !editBankAccountNumber.trim() || !editBankHolderKana.trim() || !editBankEffectiveFrom || updateBankAccountMutation.isPending}
                  >
                    {updateBankAccountMutation.isPending ? "更新中..." : "口座を更新"}
                  </button>
                  <button type="button" style={{ fontSize: "0.8rem" }} onClick={() => setSelectedBankAccount(null)}>
                    編集を閉じる
                  </button>
                </div>
              </section>
            ) : null}

            <details style={{ marginTop: "0.75rem" }}>
              <summary style={{ cursor: "pointer", fontSize: "0.85rem", color: "#4b5563" }}>口座を追加</summary>
              <div style={{ display: "grid", gap: "0.5rem", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", marginTop: "0.5rem" }}>
                <label style={{ fontSize: "0.8rem" }}>
                  銀行名 *
                  <input value={bankBankName} onChange={(e) => setBankBankName(e.target.value)} placeholder="例: ゆうちょ銀行" />
                </label>
                <label style={{ fontSize: "0.8rem" }}>
                  支店名 *
                  <input value={bankBranchName} onChange={(e) => setBankBranchName(e.target.value)} placeholder="例: 本店" />
                </label>
                <label style={{ fontSize: "0.8rem" }}>
                  支店コード
                  <input value={bankBranchCode} onChange={(e) => setBankBranchCode(e.target.value)} placeholder="任意" maxLength={10} />
                </label>
                <label style={{ fontSize: "0.8rem" }}>
                  種別 *
                  <select value={bankAccountType} onChange={(e) => setBankAccountType(e.target.value)}>
                    <option value="普通">普通</option>
                    <option value="当座">当座</option>
                    <option value="貯蓄">貯蓄</option>
                  </select>
                </label>
                <label style={{ fontSize: "0.8rem" }}>
                  口座番号 *
                  <input value={bankAccountNumber} onChange={(e) => setBankAccountNumber(e.target.value)} placeholder="例: 1234567" maxLength={20} />
                </label>
                <label style={{ fontSize: "0.8rem" }}>
                  口座名義(カナ) *
                  <input value={bankHolderKana} onChange={(e) => setBankHolderKana(e.target.value)} placeholder="例: ヤマダ タロウ" />
                </label>
                <label style={{ fontSize: "0.8rem" }}>
                  有効開始日 *
                  <input type="date" value={bankEffectiveFrom} onChange={(e) => setBankEffectiveFrom(e.target.value)} />
                </label>
                <label style={{ fontSize: "0.8rem" }}>
                  有効終了日
                  <input type="date" value={bankEffectiveUntil} onChange={(e) => setBankEffectiveUntil(e.target.value)} />
                </label>
                <label style={{ fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <input type="checkbox" checked={bankIsPrimary} onChange={(e) => setBankIsPrimary(e.target.checked)} style={{ width: "auto" }} />
                  主口座
                </label>
              </div>
              {bankFormError ? <p className="form-error" style={{ fontSize: "0.8rem" }}>{bankFormError}</p> : null}
              {bankFormMessage ? <p style={{ margin: 0, color: "#16a34a", fontSize: "0.8rem" }}>{bankFormMessage}</p> : null}
              <button
                type="button"
                style={{ marginTop: "0.5rem", fontSize: "0.8rem" }}
                onClick={() => createBankAccountMutation.mutate()}
                disabled={!bankBankName.trim() || !bankBranchName.trim() || !bankAccountNumber.trim() || !bankHolderKana.trim() || !bankEffectiveFrom || createBankAccountMutation.isPending}
              >
                {createBankAccountMutation.isPending ? "登録中..." : "口座を登録"}
              </button>
            </details>
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
