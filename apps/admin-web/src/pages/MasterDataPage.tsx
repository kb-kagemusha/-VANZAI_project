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
  createClient,
  createProjectType,
  createRole,
  createSite,
  createSupplier,
  createWorker,
  getClients,
  getProjectTypes,
  getRoles,
  getSites,
  getSuppliers,
  getWorkers,
  updateSupplier,
  updateWorker,
} from "../lib/api/client";
import type {
  ClientCreateRequest,
  ProjectTypeCreateRequest,
  RoleCreateRequest,
  SiteCreateRequest,
  SupplierCreateRequest,
  SupplierListItem,
  SupplierUpdateRequest,
  WorkerCreateRequest,
  WorkerListItem,
  WorkerUpdateRequest,
} from "../types/api";

const PAGE_SIZE = 20;

type MasterView = "workers" | "suppliers" | "clients" | "sites" | "project_types" | "roles";

type CreateMasterVariables =
  | { view: "workers"; body: WorkerCreateRequest }
  | { view: "suppliers"; body: SupplierCreateRequest }
  | { view: "clients"; body: ClientCreateRequest }
  | { view: "sites"; body: SiteCreateRequest }
  | { view: "project_types"; body: ProjectTypeCreateRequest }
  | { view: "roles"; body: RoleCreateRequest };

type UpdateMasterVariables =
  | { view: "workers"; id: string; body: WorkerUpdateRequest }
  | { view: "suppliers"; id: string; body: SupplierUpdateRequest };

const VIEW_LABELS: Record<MasterView, string> = {
  workers: "稼働者",
  suppliers: "下請け",
  clients: "クライアント",
  sites: "現場",
  project_types: "案件種別",
  roles: "役割",
};

export function MasterDataPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [view, setView] = useState<MasterView>("workers");
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [isActive, setIsActive] = useState("");
  const [createName, setCreateName] = useState("");
  const [createCode, setCreateCode] = useState("");
  const [createEmail, setCreateEmail] = useState("");
  const [createPhone, setCreatePhone] = useState("");
  const [createSupplierId, setCreateSupplierId] = useState("");
  const [createContactName, setCreateContactName] = useState("");
  const [createContactEmail, setCreateContactEmail] = useState("");
  const [createContactPhone, setCreateContactPhone] = useState("");
  const [createAddress, setCreateAddress] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createTermsDays, setCreateTermsDays] = useState("70");
  const [createDefaultDailyPrice, setCreateDefaultDailyPrice] = useState("");
  const [createNotes, setCreateNotes] = useState("");
  const [createIsActive, setCreateIsActive] = useState(true);
  const [selectedWorker, setSelectedWorker] = useState<WorkerListItem | null>(null);
  const [selectedSupplier, setSelectedSupplier] = useState<SupplierListItem | null>(null);
  const [editName, setEditName] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editSupplierId, setEditSupplierId] = useState("");
  const [editContactPhone, setEditContactPhone] = useState("");
  const [editTermsDays, setEditTermsDays] = useState("70");
  const [editDefaultDailyPrice, setEditDefaultDailyPrice] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editIsActive, setEditIsActive] = useState(true);
  const [formError, setFormError] = useState("");
  const [formMessage, setFormMessage] = useState("");
  const [editError, setEditError] = useState("");
  const [editMessage, setEditMessage] = useState("");

  function resetCreateForm() {
    setCreateName("");
    setCreateCode("");
    setCreateEmail("");
    setCreatePhone("");
    setCreateSupplierId("");
    setCreateContactName("");
    setCreateContactEmail("");
    setCreateContactPhone("");
    setCreateAddress("");
    setCreateDescription("");
    setCreateTermsDays("70");
    setCreateDefaultDailyPrice("");
    setCreateNotes("");
    setCreateIsActive(true);
    setFormError("");
    setFormMessage("");
  }

  function clearEditor() {
    setSelectedWorker(null);
    setSelectedSupplier(null);
    setEditName("");
    setEditEmail("");
    setEditPhone("");
    setEditSupplierId("");
    setEditContactPhone("");
    setEditTermsDays("70");
    setEditDefaultDailyPrice("");
    setEditNotes("");
    setEditIsActive(true);
    setEditError("");
    setEditMessage("");
  }

  function handleViewChange(next: MasterView) {
    setView(next);
    setPage(0);
    setSearch("");
    setIsActive("");
    resetCreateForm();
    clearEditor();
  }

  function openWorkerEditor(worker: WorkerListItem) {
    setSelectedSupplier(null);
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

  function openSupplierEditor(supplier: SupplierListItem) {
    setSelectedWorker(null);
    setSelectedSupplier(supplier);
    setEditName(supplier.name);
    setEditEmail(supplier.contact_email ?? "");
    setEditContactPhone(supplier.contact_phone ?? "");
    setEditTermsDays(String(supplier.payout_terms_days));
    setEditDefaultDailyPrice(supplier.default_daily_price ?? "");
    setEditNotes(supplier.notes ?? "");
    setEditIsActive(supplier.is_active);
    setEditError("");
    setEditMessage("");
  }

  const commonParams = {
    search: search || undefined,
    offset: page * PAGE_SIZE,
    limit: PAGE_SIZE,
  };

  const workersQuery = useQuery({
    queryKey: ["workers-page", search, isActive, page],
    queryFn: () => getWorkers({ ...commonParams, is_active: isActive === "" ? undefined : isActive === "true" }),
    enabled: view === "workers",
  });

  const suppliersQuery = useQuery({
    queryKey: ["suppliers-page", search, isActive, page],
    queryFn: () => getSuppliers({ ...commonParams, is_active: isActive === "" ? undefined : isActive === "true" }),
    enabled: view === "suppliers",
  });

  const supplierOptionsQuery = useQuery({
    queryKey: ["suppliers-master-options"],
    queryFn: () => getSuppliers({ limit: 200, sort_by: "name", sort_order: "asc", is_active: true }),
    enabled: user?.role === "admin",
  });

  const clientsQuery = useQuery({
    queryKey: ["clients-page", search, page],
    queryFn: () => getClients(commonParams),
    enabled: view === "clients",
  });

  const sitesQuery = useQuery({
    queryKey: ["sites-page", search, page],
    queryFn: () => getSites(commonParams),
    enabled: view === "sites",
  });

  const projectTypesQuery = useQuery({
    queryKey: ["project-types-page", search, page],
    queryFn: () => getProjectTypes(commonParams),
    enabled: view === "project_types",
  });

  const rolesQuery = useQuery({
    queryKey: ["roles-page", search, page],
    queryFn: () => getRoles(commonParams),
    enabled: view === "roles",
  });

  const activeQuery =
    view === "workers"
      ? workersQuery
      : view === "suppliers"
        ? suppliersQuery
        : view === "clients"
          ? clientsQuery
          : view === "sites"
            ? sitesQuery
            : view === "project_types"
              ? projectTypesQuery
              : rolesQuery;

  const createMutation = useMutation<unknown, unknown, CreateMasterVariables>({
    mutationFn: async (variables) => {
      switch (variables.view) {
        case "workers":
          return createWorker(variables.body);
        case "suppliers":
          return createSupplier(variables.body);
        case "clients":
          return createClient(variables.body);
        case "sites":
          return createSite(variables.body);
        case "project_types":
          return createProjectType(variables.body);
        case "roles":
          return createRole(variables.body);
      }
    },
    onSuccess: async (_, variables) => {
      resetCreateForm();
      setPage(0);
      setFormMessage(`${VIEW_LABELS[variables.view]}を作成しました`);

      await queryClient.invalidateQueries({ queryKey: [`${variables.view === "project_types" ? "project-types" : variables.view}-page`] });
      if (variables.view === "workers" || variables.view === "suppliers") {
        await queryClient.invalidateQueries({ queryKey: ["suppliers-master-options"] });
      }
      if (variables.view === "clients") {
        await queryClient.invalidateQueries({ queryKey: ["clients-project-form"] });
      }
      if (variables.view === "sites") {
        await queryClient.invalidateQueries({ queryKey: ["sites-project-form"] });
      }
      if (variables.view === "project_types") {
        await queryClient.invalidateQueries({ queryKey: ["project-types-project-form"] });
      }
      if (variables.view === "roles") {
        await queryClient.invalidateQueries({ queryKey: ["roles-page"] });
      }
    },
    onError: (error: unknown) => {
      setFormMessage("");
      setFormError(error instanceof ApiError ? error.message : "マスタ作成に失敗しました");
    },
  });

  const updateMutation = useMutation<unknown, unknown, UpdateMasterVariables>({
    mutationFn: async (variables) => {
      switch (variables.view) {
        case "workers":
          return updateWorker(variables.id, variables.body);
        case "suppliers":
          return updateSupplier(variables.id, variables.body);
      }
    },
    onSuccess: async (_, variables) => {
      setEditError("");
      setEditMessage(`${VIEW_LABELS[variables.view]}を更新しました`);
      await queryClient.invalidateQueries({ queryKey: [`${variables.view}-page`] });
      await queryClient.invalidateQueries({ queryKey: ["suppliers-master-options"] });
    },
    onError: (error: unknown) => {
      setEditMessage("");
      setEditError(error instanceof ApiError ? error.message : "更新に失敗しました");
    },
  });

  function handleCreate() {
    if (user?.role !== "admin") {
      return;
    }
    setFormError("");
    setFormMessage("");

    switch (view) {
      case "workers":
        createMutation.mutate({
          view,
          body: {
            name: createName,
            email: createEmail || null,
            phone: createPhone || null,
            introducer_supplier_id: createSupplierId || null,
            notes: createNotes || null,
            is_active: createIsActive,
          },
        });
        break;
      case "suppliers":
        createMutation.mutate({
          view,
          body: {
            name: createName,
            contact_email: createContactEmail || null,
            contact_phone: createContactPhone || null,
            payout_terms_days: Number(createTermsDays || 70),
            default_daily_price: createDefaultDailyPrice || null,
            is_active: createIsActive,
            notes: createNotes || null,
          },
        });
        break;
      case "clients":
        createMutation.mutate({ view, body: { name: createName, code: createCode || null, address: createAddress || null, contact_name: createContactName || null, contact_email: createContactEmail || null } });
        break;
      case "sites":
        createMutation.mutate({ view, body: { name: createName, code: createCode || null, address: createAddress || null } });
        break;
      case "project_types":
        createMutation.mutate({ view, body: { name: createName, code: createCode || null, description: createDescription || null } });
        break;
      case "roles":
        createMutation.mutate({ view, body: { name: createName, code: createCode || null, description: createDescription || null } });
        break;
    }
  }

  function handleUpdate() {
    if (user?.role !== "admin") {
      return;
    }
    setEditError("");
    setEditMessage("");

    if (selectedWorker) {
      updateMutation.mutate({
        view: "workers",
        id: selectedWorker.id,
        body: {
          name: editName,
          email: editEmail || null,
          phone: editPhone || null,
          introducer_supplier_id: editSupplierId || null,
          notes: editNotes || null,
          is_active: editIsActive,
        },
      });
      return;
    }

    if (selectedSupplier) {
      updateMutation.mutate({
        view: "suppliers",
        id: selectedSupplier.id,
        body: {
          name: editName,
          contact_email: editEmail || null,
          contact_phone: editContactPhone || null,
          payout_terms_days: Number(editTermsDays || 70),
          default_daily_price: editDefaultDailyPrice || null,
          is_active: editIsActive,
          notes: editNotes || null,
        },
      });
    }
  }

  if (activeQuery.isLoading) {
    return <LoadingOverlay label="マスタ一覧を読み込み中..." />;
  }

  if (activeQuery.error instanceof ApiError && activeQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (activeQuery.isError || !activeQuery.data) {
    return <ErrorState title="マスタ一覧の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  const total = activeQuery.data.total;
  const showActiveFilter = view === "workers" || view === "suppliers";
  const canEditMaster = user?.role === "admin" && (selectedWorker || selectedSupplier);

  return (
    <div className="page-stack">
      <PageHeader title="マスタ一覧" description="稼働者・下請け・クライアント等のマスタデータを参照します。" />

      <section className="upload-card">
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
          <strong>表示切替</strong>
          {(Object.keys(VIEW_LABELS) as MasterView[]).map((v) => (
            <button key={v} type="button" onClick={() => handleViewChange(v)} style={{ opacity: view === v ? 1 : 0.7 }}>
              {VIEW_LABELS[v]}
            </button>
          ))}
        </div>
      </section>

      {user?.role === "admin" ? (
        <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
          <strong>{VIEW_LABELS[view]}を追加</strong>
          <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
            <label>
              名称
              <input value={createName} onChange={(event) => setCreateName(event.target.value)} placeholder="名称" />
            </label>

            {(view === "clients" || view === "sites" || view === "project_types" || view === "roles") ? (
              <label>
                コード
                <input value={createCode} onChange={(event) => setCreateCode(event.target.value)} placeholder="任意" />
              </label>
            ) : null}

            {view === "workers" ? (
              <>
                <label>
                  メール
                  <input value={createEmail} onChange={(event) => setCreateEmail(event.target.value)} placeholder="任意" />
                </label>
                <label>
                  電話
                  <input value={createPhone} onChange={(event) => setCreatePhone(event.target.value)} placeholder="任意" />
                </label>
                <label>
                  紹介会社
                  <select value={createSupplierId} onChange={(event) => setCreateSupplierId(event.target.value)}>
                    <option value="">未設定</option>
                    {(supplierOptionsQuery.data?.items ?? []).map((item) => (
                      <option key={item.id} value={item.id}>{item.name}</option>
                    ))}
                  </select>
                </label>
              </>
            ) : null}

            {view === "suppliers" ? (
              <>
                <label>
                  メール
                  <input value={createContactEmail} onChange={(event) => setCreateContactEmail(event.target.value)} placeholder="任意" />
                </label>
                <label>
                  電話
                  <input value={createContactPhone} onChange={(event) => setCreateContactPhone(event.target.value)} placeholder="任意" />
                </label>
                <label>
                  支払サイト(日)
                  <input type="number" min="0" value={createTermsDays} onChange={(event) => setCreateTermsDays(event.target.value)} />
                </label>
                <label>
                  日額単価
                  <input value={createDefaultDailyPrice} onChange={(event) => setCreateDefaultDailyPrice(event.target.value)} placeholder="任意" />
                </label>
              </>
            ) : null}

            {view === "clients" ? (
              <>
                <label>
                  担当者
                  <input value={createContactName} onChange={(event) => setCreateContactName(event.target.value)} placeholder="任意" />
                </label>
                <label>
                  メール
                  <input value={createContactEmail} onChange={(event) => setCreateContactEmail(event.target.value)} placeholder="任意" />
                </label>
              </>
            ) : null}
          </div>

          {(view === "clients" || view === "sites") ? (
            <label>
              住所
              <textarea value={createAddress} onChange={(event) => setCreateAddress(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} />
            </label>
          ) : null}

          {(view === "workers" || view === "suppliers") ? (
            <>
              <label>
                メモ
                <textarea value={createNotes} onChange={(event) => setCreateNotes(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} />
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input type="checkbox" checked={createIsActive} onChange={(event) => setCreateIsActive(event.target.checked)} />
                有効
              </label>
            </>
          ) : null}

          {(view === "project_types" || view === "roles") ? (
            <label>
              説明
              <textarea value={createDescription} onChange={(event) => setCreateDescription(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} />
            </label>
          ) : null}

          {formError ? <p className="form-error">{formError}</p> : null}
          {formMessage ? <p>{formMessage}</p> : null}
          <div>
            <button type="button" className="primary-button" onClick={handleCreate} disabled={!createName.trim() || createMutation.isPending}>
              {createMutation.isPending ? "作成中..." : `${VIEW_LABELS[view]}を追加`}
            </button>
          </div>
        </section>
      ) : null}

      {canEditMaster ? (
        <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
          <strong>{selectedWorker ? "稼働者を編集" : "下請けを編集"}</strong>
          <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
            <label>
              名称
              <input value={editName} onChange={(event) => setEditName(event.target.value)} />
            </label>
            <label>
              メール
              <input value={editEmail} onChange={(event) => setEditEmail(event.target.value)} />
            </label>
            {selectedWorker ? (
              <>
                <label>
                  電話
                  <input value={editPhone} onChange={(event) => setEditPhone(event.target.value)} />
                </label>
                <label>
                  紹介会社
                  <select value={editSupplierId} onChange={(event) => setEditSupplierId(event.target.value)}>
                    <option value="">未設定</option>
                    {(supplierOptionsQuery.data?.items ?? []).map((item) => (
                      <option key={item.id} value={item.id}>{item.name}</option>
                    ))}
                  </select>
                </label>
              </>
            ) : null}
            {selectedSupplier ? (
              <>
                <label>
                  電話
                  <input value={editContactPhone} onChange={(event) => setEditContactPhone(event.target.value)} />
                </label>
                <label>
                  支払サイト(日)
                  <input type="number" min="0" value={editTermsDays} onChange={(event) => setEditTermsDays(event.target.value)} />
                </label>
                <label>
                  日額単価
                  <input value={editDefaultDailyPrice} onChange={(event) => setEditDefaultDailyPrice(event.target.value)} />
                </label>
              </>
            ) : null}
          </div>
          <label>
            メモ
            <textarea value={editNotes} onChange={(event) => setEditNotes(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <input type="checkbox" checked={editIsActive} onChange={(event) => setEditIsActive(event.target.checked)} />
            有効
          </label>
          {editError ? <p className="form-error">{editError}</p> : null}
          {editMessage ? <p>{editMessage}</p> : null}
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <button type="button" className="primary-button" onClick={handleUpdate} disabled={!editName.trim() || updateMutation.isPending}>
              {updateMutation.isPending ? "更新中..." : "更新する"}
            </button>
            <button type="button" onClick={clearEditor}>編集を閉じる</button>
          </div>
        </section>
      ) : null}

      <FilterBar>
        <label>
          検索
          <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(0); }} placeholder={`${VIEW_LABELS[view]}名で検索`} />
        </label>
        {showActiveFilter ? (
          <label>
            状態
            <select value={isActive} onChange={(e) => { setIsActive(e.target.value); setPage(0); }}>
              <option value="">すべて</option>
              <option value="true">有効のみ</option>
              <option value="false">無効のみ</option>
            </select>
          </label>
        ) : null}
      </FilterBar>

      {view === "workers" ? (
        <DataTable
          columns={[
            { key: "name", header: "氏名", render: (row) => row.name },
            { key: "email", header: "メール", render: (row) => row.email ?? "—" },
            { key: "phone", header: "電話", render: (row) => row.phone ?? "—" },
            { key: "supplier", header: "紹介会社", render: (row) => row.introducer_supplier_name ?? "—" },
            { key: "status", header: "有効", render: (row) => <span className={`status-badge ${row.is_active ? "active" : "inactive"}`}>{row.is_active ? "有効" : "無効"}</span> },
            { key: "actions", header: "操作", render: (row) => user?.role === "admin" ? <button type="button" onClick={() => openWorkerEditor(row)}>編集</button> : "—" },
          ]}
          rows={workersQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="稼働者はいません"
          emptyDescription="CSV取り込みまたは直接登録で追加してください。"
        />
      ) : null}

      {view === "suppliers" ? (
        <DataTable
          columns={[
            { key: "name", header: "会社名", render: (row) => row.name },
            { key: "email", header: "メール", render: (row) => row.contact_email ?? "—" },
            { key: "phone", header: "電話", render: (row) => row.contact_phone ?? "—" },
            { key: "terms", header: "支払サイト(日)", render: (row) => String(row.payout_terms_days) },
            { key: "price", header: "日額単価", render: (row) => row.default_daily_price != null ? `¥${Number(row.default_daily_price).toLocaleString()}` : "—" },
            { key: "status", header: "有効", render: (row) => <span className={`status-badge ${row.is_active ? "active" : "inactive"}`}>{row.is_active ? "有効" : "無効"}</span> },
            { key: "actions", header: "操作", render: (row) => user?.role === "admin" ? <button type="button" onClick={() => openSupplierEditor(row)}>編集</button> : "—" },
          ]}
          rows={suppliersQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="下請けはいません"
          emptyDescription="CSV取り込みまたは直接登録で追加してください。"
        />
      ) : null}

      {view === "clients" ? (
        <DataTable
          columns={[
            { key: "name", header: "名称", render: (row) => row.name },
            { key: "code", header: "コード", render: (row) => row.code ?? "—" },
            { key: "contact_name", header: "担当者", render: (row) => row.contact_name ?? "—" },
            { key: "contact_email", header: "メール", render: (row) => row.contact_email ?? "—" },
          ]}
          rows={clientsQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="クライアントはいません"
          emptyDescription="CSV取り込みまたは直接登録で追加してください。"
        />
      ) : null}

      {view === "sites" ? (
        <DataTable
          columns={[
            { key: "name", header: "現場名", render: (row) => row.name },
            { key: "code", header: "コード", render: (row) => row.code ?? "—" },
            { key: "address", header: "住所", render: (row) => row.address ?? "—" },
          ]}
          rows={sitesQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="現場はありません"
          emptyDescription="CSV取り込みまたは直接登録で追加してください。"
        />
      ) : null}

      {view === "project_types" ? (
        <DataTable
          columns={[
            { key: "name", header: "種別名", render: (row) => row.name },
            { key: "code", header: "コード", render: (row) => row.code ?? "—" },
            { key: "description", header: "説明", render: (row) => row.description ?? "—" },
          ]}
          rows={projectTypesQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="案件種別はありません"
          emptyDescription="CSV取り込みまたは直接登録で追加してください。"
        />
      ) : null}

      {view === "roles" ? (
        <DataTable
          columns={[
            { key: "name", header: "役割名", render: (row) => row.name },
            { key: "code", header: "コード", render: (row) => row.code ?? "—" },
            { key: "description", header: "説明", render: (row) => row.description ?? "—" },
          ]}
          rows={rolesQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="役割はありません"
          emptyDescription="CSV取り込みまたは直接登録で追加してください。"
        />
      ) : null}

      <PaginationBar page={page} total={total} limit={PAGE_SIZE} onPrevious={() => setPage((p) => Math.max(0, p - 1))} onNext={() => setPage((p) => p + 1)} />
    </div>
  );
}