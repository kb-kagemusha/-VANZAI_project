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
import { ApiError, getProjects } from "../lib/api/client";
import { formatDate } from "../lib/formatters";

const PAGE_SIZE = 20;

export function ProjectsPage() {
  const [search, setSearch] = useState("");
  const [isActive, setIsActive] = useState("");
  const [sortBy, setSortBy] = useState("name");
  const [sortOrder, setSortOrder] = useState("asc");
  const [page, setPage] = useState(0);

  const projectsQuery = useQuery({
    queryKey: ["projects", search, isActive, sortBy, sortOrder, page],
    queryFn: () =>
      getProjects({
        search: search || undefined,
        is_active: isActive === "" ? undefined : isActive === "true",
        sort_by: sortBy,
        sort_order: sortOrder,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
  });

  if (projectsQuery.isLoading) {
    return <LoadingOverlay label="案件一覧を読み込み中..." />;
  }

  if (projectsQuery.error instanceof ApiError && projectsQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (projectsQuery.isError || !projectsQuery.data) {
    return <ErrorState title="案件一覧の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  return (
    <div className="page-stack">
      <PageHeader title="案件一覧" description="案件、取引先、現場、期間、稼働状態を確認します。" />
      <FilterBar>
        <label>
          検索
          <input value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder="案件名、コード、取引先" />
        </label>
        <label>
          稼働状態
          <select value={isActive} onChange={(event) => { setIsActive(event.target.value); setPage(0); }}>
            <option value="">すべて</option>
            <option value="true">有効</option>
            <option value="false">無効</option>
          </select>
        </label>
        <label>
          ソート
          <select value={sortBy} onChange={(event) => { setSortBy(event.target.value); setPage(0); }}>
            <option value="name">案件名</option>
            <option value="code">コード</option>
            <option value="client_name">取引先名</option>
            <option value="site_name">現場名</option>
            <option value="start_date">開始日</option>
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
          { key: "code", header: "コード", render: (row) => row.code || "-" },
          { key: "name", header: "案件", render: (row) => row.name },
          { key: "client", header: "取引先", render: (row) => row.client_name },
          { key: "site", header: "現場", render: (row) => row.site_name },
          { key: "type", header: "案件種別", render: (row) => row.project_type_name },
          { key: "start", header: "開始日", render: (row) => formatDate(row.start_date) },
          { key: "end", header: "終了日", render: (row) => formatDate(row.end_date) },
          { key: "status", header: "状態", render: (row) => <StatusBadge value={row.is_active ? "active" : "inactive"} /> },
        ]}
        rows={projectsQuery.data.items}
        getRowKey={(row) => row.id}
        emptyTitle="案件はありません"
        emptyDescription="条件に一致する案件は見つかりませんでした。"
      />

      <PaginationBar
        page={page}
        total={projectsQuery.data.total}
        limit={projectsQuery.data.limit}
        onPrevious={() => setPage((value) => Math.max(0, value - 1))}
        onNext={() => setPage((value) => value + 1)}
      />
    </div>
  );
}