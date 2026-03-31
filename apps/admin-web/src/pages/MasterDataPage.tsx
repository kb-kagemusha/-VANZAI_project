import { Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { PaginationBar } from "../components/PaginationBar";
import {
  ApiError,
  getClients,
  getProjectTypes,
  getRoles,
  getSites,
  getSuppliers,
  getWorkers,
} from "../lib/api/client";

const PAGE_SIZE = 20;

type MasterView = "workers" | "suppliers" | "clients" | "sites" | "project_types" | "roles";

const VIEW_LABELS: Record<MasterView, string> = {
  workers: "稼働者",
  suppliers: "下請け",
  clients: "クライアント",
  sites: "現場",
  project_types: "案件種別",
  roles: "役割",
};

export function MasterDataPage() {
  const [view, setView] = useState<MasterView>("workers");
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [isActive, setIsActive] = useState("");

  function handleViewChange(next: MasterView) {
    setView(next);
    setPage(0);
    setSearch("");
    setIsActive("");
  }

  const commonParams = {
    search: search || undefined,
    offset: page * PAGE_SIZE,
    limit: PAGE_SIZE,
  };

  const workersQuery = useQuery({
    queryKey: ["workers-page", search, isActive, page],
    queryFn: () =>
      getWorkers({
        ...commonParams,
        is_active: isActive === "" ? undefined : isActive === "true",
      }),
    enabled: view === "workers",
  });

  const suppliersQuery = useQuery({
    queryKey: ["suppliers-page", search, isActive, page],
    queryFn: () =>
      getSuppliers({
        ...commonParams,
        is_active: isActive === "" ? undefined : isActive === "true",
      }),
    enabled: view === "suppliers",
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

  if (activeQuery.isLoading) {
    return <LoadingOverlay label="マスタ一覧を読み込み中..." />;
  }

  if (activeQuery.error instanceof ApiError && activeQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (activeQuery.isError || !activeQuery.data) {
    return (
      <ErrorState
        title="マスタ一覧の取得に失敗しました"
        description="認証または API 疎通を確認してください。"
      />
    );
  }

  const total = activeQuery.data.total;
  const showActiveFilter = view === "workers" || view === "suppliers";

  return (
    <div className="page-stack">
      <PageHeader title="マスタ一覧" description="稼働者・下請け・クライアント等のマスタデータを参照します。" />

      <section className="upload-card">
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
          <strong>表示切替</strong>
          {(Object.keys(VIEW_LABELS) as MasterView[]).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => handleViewChange(v)}
              style={{ opacity: view === v ? 1 : 0.7 }}
            >
              {VIEW_LABELS[v]}
            </button>
          ))}
        </div>
      </section>

      <FilterBar>
        <label>
          検索
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            placeholder={`${VIEW_LABELS[view]}名で検索`}
          />
        </label>
        {showActiveFilter && (
          <label>
            状態
            <select
              value={isActive}
              onChange={(e) => {
                setIsActive(e.target.value);
                setPage(0);
              }}
            >
              <option value="">すべて</option>
              <option value="true">有効のみ</option>
              <option value="false">無効のみ</option>
            </select>
          </label>
        )}
      </FilterBar>

      {view === "workers" && (
        <DataTable
          columns={[
            { key: "name", header: "氏名", render: (row) => row.name },
            { key: "email", header: "メール", render: (row) => row.email ?? "—" },
            { key: "phone", header: "電話", render: (row) => row.phone ?? "—" },
            { key: "supplier", header: "紹介会社", render: (row) => row.introducer_supplier_name ?? "—" },
            { key: "status", header: "有効", render: (row) => (row.is_active ? "有効" : "無効") },
          ]}
          rows={workersQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="稼働者はいません"
          emptyDescription="CSV取り込みまたは直接登録で追加してください。"
        />
      )}

      {view === "suppliers" && (
        <DataTable
          columns={[
            { key: "name", header: "会社名", render: (row) => row.name },
            { key: "email", header: "メール", render: (row) => row.contact_email ?? "—" },
            { key: "terms", header: "支払サイト(日)", render: (row) => String(row.payout_terms_days) },
            { key: "price", header: "日額単価", render: (row) => row.default_daily_price != null ? `¥${Number(row.default_daily_price).toLocaleString()}` : "—" },
            { key: "status", header: "有効", render: (row) => (row.is_active ? "有効" : "無効") },
          ]}
          rows={suppliersQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="下請けはいません"
          emptyDescription="CSV取り込みまたは直接登録で追加してください。"
        />
      )}

      {view === "clients" && (
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
      )}

      {view === "sites" && (
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
      )}

      {view === "project_types" && (
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
      )}

      {view === "roles" && (
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
      )}

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
