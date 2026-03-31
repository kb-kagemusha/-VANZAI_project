import { Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { PaginationBar } from "../components/PaginationBar";
import { StatusBadge } from "../components/StatusBadge";
import { ApiError, getPriceOutsource, getPriceRules, getPriceSales } from "../lib/api/client";
import { formatCurrency, formatDate } from "../lib/formatters";

const PAGE_SIZE = 20;

type PriceView = "sales" | "outsource" | "rules";

function formatUnitType(unitType: string): string {
  const labels: Record<string, string> = {
    hourly: "時給",
    daily: "日給",
    monthly: "月額",
    fixed: "固定",
  };

  return labels[unitType] || unitType;
}

export function PriceManagementPage() {
  const [priceView, setPriceView] = useState<PriceView>("sales");
  const [page, setPage] = useState(0);
  const [sortOrder, setSortOrder] = useState("desc");
  const [defaultOnly, setDefaultOnly] = useState("");
  const [activeOnly, setActiveOnly] = useState("");
  const [search, setSearch] = useState("");
  const [salesSortBy, setSalesSortBy] = useState("valid_from");
  const [outsourceSortBy, setOutsourceSortBy] = useState("valid_from");
  const [ruleSortBy, setRuleSortBy] = useState("priority");

  const salesQuery = useQuery({
    queryKey: ["price-sales-page", defaultOnly, salesSortBy, sortOrder, page],
    queryFn: () =>
      getPriceSales({
        is_default: defaultOnly === "" ? undefined : defaultOnly === "true",
        sort_by: salesSortBy,
        sort_order: sortOrder,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    enabled: priceView === "sales",
  });

  const outsourceQuery = useQuery({
    queryKey: ["price-outsource-page", defaultOnly, outsourceSortBy, sortOrder, page],
    queryFn: () =>
      getPriceOutsource({
        is_default: defaultOnly === "" ? undefined : defaultOnly === "true",
        sort_by: outsourceSortBy,
        sort_order: sortOrder,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    enabled: priceView === "outsource",
  });

  const rulesQuery = useQuery({
    queryKey: ["price-rules-page", search, activeOnly, ruleSortBy, sortOrder, page],
    queryFn: () =>
      getPriceRules({
        search: search || undefined,
        is_active: activeOnly === "" ? undefined : activeOnly === "true",
        sort_by: ruleSortBy,
        sort_order: sortOrder,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    enabled: priceView === "rules",
  });

  const activeQuery = priceView === "sales" ? salesQuery : priceView === "outsource" ? outsourceQuery : rulesQuery;

  if (activeQuery.isLoading) {
    return <LoadingOverlay label="単価一覧を読み込み中..." />;
  }

  if (activeQuery.error instanceof ApiError && activeQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (activeQuery.isError || !activeQuery.data) {
    return <ErrorState title="単価一覧の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  return (
    <div className="page-stack">
      <PageHeader title="単価一覧" description="売上単価、外注単価、単価ルールを参照専用で確認します。" />
      <section className="upload-card">
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
          <strong>表示切替</strong>
          <button type="button" onClick={() => { setPriceView("sales"); setPage(0); }} style={{ opacity: priceView === "sales" ? 1 : 0.7 }}>
            売上単価
          </button>
          <button type="button" onClick={() => { setPriceView("outsource"); setPage(0); }} style={{ opacity: priceView === "outsource" ? 1 : 0.7 }}>
            外注単価
          </button>
          <button type="button" onClick={() => { setPriceView("rules"); setPage(0); }} style={{ opacity: priceView === "rules" ? 1 : 0.7 }}>
            単価ルール
          </button>
        </div>
        <p style={{ margin: "0.5rem 0 0", color: "var(--color-muted)" }}>
          {priceView === "sales"
            ? "案件・取引先・役割に紐づく売上単価を確認します。"
            : priceView === "outsource"
              ? "案件・稼働者・役割に紐づく外注単価を確認します。"
              : "条件ベースの単価ルールと優先順位を確認します。"}
        </p>
      </section>
      <FilterBar>
        {priceView === "rules" ? (
          <>
            <label>
              検索
              <input value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder="ルール名" />
            </label>
            <label>
              稼働状態
              <select value={activeOnly} onChange={(event) => { setActiveOnly(event.target.value); setPage(0); }}>
                <option value="">すべて</option>
                <option value="true">有効のみ</option>
                <option value="false">無効のみ</option>
              </select>
            </label>
            <label>
              ソート
              <select value={ruleSortBy} onChange={(event) => { setRuleSortBy(event.target.value); setPage(0); }}>
                <option value="priority">優先順位</option>
                <option value="name">ルール名</option>
                <option value="valid_from">開始日</option>
                <option value="valid_to">終了日</option>
              </select>
            </label>
          </>
        ) : (
          <>
            <label>
              既定単価
              <select value={defaultOnly} onChange={(event) => { setDefaultOnly(event.target.value); setPage(0); }}>
                <option value="">すべて</option>
                <option value="true">既定のみ</option>
                <option value="false">個別のみ</option>
              </select>
            </label>
            <label>
              ソート
              <select
                value={priceView === "sales" ? salesSortBy : outsourceSortBy}
                onChange={(event) => {
                  if (priceView === "sales") {
                    setSalesSortBy(event.target.value);
                  } else {
                    setOutsourceSortBy(event.target.value);
                  }
                  setPage(0);
                }}
              >
                <option value="valid_from">開始日</option>
                <option value="valid_to">終了日</option>
                <option value="unit_price">単価</option>
                <option value="project_name">案件名</option>
                <option value="role_name">役割名</option>
                {priceView === "sales" ? <option value="client_name">取引先名</option> : <option value="worker_name">稼働者名</option>}
              </select>
            </label>
          </>
        )}
        <label>
          順序
          <select value={sortOrder} onChange={(event) => { setSortOrder(event.target.value); setPage(0); }}>
            <option value="desc">降順</option>
            <option value="asc">昇順</option>
          </select>
        </label>
      </FilterBar>

      {priceView === "sales" ? (
        <DataTable
          columns={[
            { key: "project", header: "案件", render: (row) => row.project_name || "既定単価" },
            { key: "client", header: "取引先", render: (row) => row.client_name || "-" },
            { key: "role", header: "役割", render: (row) => row.role_name || "-" },
            { key: "price", header: "単価", render: (row) => formatCurrency(row.unit_price) },
            { key: "unitType", header: "単位", render: (row) => formatUnitType(row.unit_type) },
            { key: "validFrom", header: "開始日", render: (row) => formatDate(row.valid_from) },
            { key: "validTo", header: "終了日", render: (row) => formatDate(row.valid_to) },
            { key: "default", header: "適用", render: (row) => (row.is_default ? "既定" : "個別") },
          ]}
          rows={salesQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="売上単価はありません"
          emptyDescription="条件に一致する売上単価は見つかりませんでした。"
        />
      ) : null}

      {priceView === "outsource" ? (
        <DataTable
          columns={[
            { key: "project", header: "案件", render: (row) => row.project_name || "既定単価" },
            { key: "worker", header: "稼働者", render: (row) => row.worker_name || "-" },
            { key: "role", header: "役割", render: (row) => row.role_name || "-" },
            { key: "price", header: "単価", render: (row) => formatCurrency(row.unit_price) },
            { key: "unitType", header: "単位", render: (row) => formatUnitType(row.unit_type) },
            { key: "validFrom", header: "開始日", render: (row) => formatDate(row.valid_from) },
            { key: "validTo", header: "終了日", render: (row) => formatDate(row.valid_to) },
            { key: "default", header: "適用", render: (row) => (row.is_default ? "既定" : "個別") },
          ]}
          rows={outsourceQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="外注単価はありません"
          emptyDescription="条件に一致する外注単価は見つかりませんでした。"
        />
      ) : null}

      {priceView === "rules" ? (
        <DataTable
          columns={[
            { key: "priority", header: "優先順位", render: (row) => row.priority },
            { key: "name", header: "ルール名", render: (row) => row.name },
            { key: "salesPrice", header: "売上単価", render: (row) => formatCurrency(row.sales_price) },
            { key: "outsourcePrice", header: "外注単価", render: (row) => formatCurrency(row.outsource_price) },
            { key: "validFrom", header: "開始日", render: (row) => formatDate(row.valid_from) },
            { key: "validTo", header: "終了日", render: (row) => formatDate(row.valid_to) },
            { key: "status", header: "状態", render: (row) => <StatusBadge value={row.is_active ? "active" : "inactive"} /> },
          ]}
          rows={rulesQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="単価ルールはありません"
          emptyDescription="条件に一致する単価ルールは見つかりませんでした。"
        />
      ) : null}

      <PaginationBar
        page={page}
        total={activeQuery.data.total}
        limit={activeQuery.data.limit}
        onPrevious={() => setPage((value) => Math.max(0, value - 1))}
        onNext={() => setPage((value) => value + 1)}
      />
    </div>
  );
}