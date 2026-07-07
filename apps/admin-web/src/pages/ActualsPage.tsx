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
import { ApiError, getActuals } from "../lib/api/client";
import { currentMonthInput, formatCurrency, formatDate, minutesToHours, toPeriodKey } from "../lib/formatters";

const PAGE_SIZE = 20;

export function ActualsPage() {
  const [monthValue, setMonthValue] = useState(currentMonthInput());
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const periodKey = toPeriodKey(monthValue);

  const actualsQuery = useQuery({
    queryKey: ["actuals", periodKey, status, page],
    queryFn: () =>
      getActuals({
        period_key: periodKey,
        status: status || undefined,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
  });

  if (actualsQuery.isLoading) {
    return <LoadingOverlay label="実績一覧を読み込み中..." />;
  }

  if (actualsQuery.error instanceof ApiError && actualsQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (actualsQuery.isError || !actualsQuery.data) {
    return <ErrorState title="実績一覧の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  return (
    <div className="page-stack">
      <PageHeader title="実績一覧" description="実績の参照、要レビュー状態、適用単価を一覧で確認します。" />
      <FilterBar className="actuals-filter-bar">
        <label>
          対象月
          <input type="month" value={monthValue} onChange={(event) => { setMonthValue(event.target.value); setPage(0); }} />
        </label>
        <label>
          ステータス
          <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(0); }}>
            <option value="">すべて</option>
            <option value="active">有効</option>
            <option value="invalid">無効</option>
          </select>
        </label>
      </FilterBar>

      <DataTable
        columns={[
          { key: "date", header: "日付", render: (row) => formatDate(row.work_date) },
          { key: "project", header: "案件", render: (row) => row.project_name },
          { key: "worker", header: "稼働者", render: (row) => row.worker_name },
          { key: "role", header: "役割", render: (row) => row.role_name },
          { key: "minutes", header: "請求時間", render: (row) => minutesToHours(row.calc_minutes_billable) },
          { key: "sales", header: "売上単価", render: (row) => formatCurrency(row.applied_price_sales) },
          { key: "outsource", header: "外注単価", render: (row) => formatCurrency(row.applied_price_outsource) },
          { key: "status", header: "状態", render: (row) => <StatusBadge value={row.status} /> },
          { key: "review", header: "レビュー", render: (row) => (row.needs_review ? row.review_reason || "要確認" : "-") },
        ]}
        rows={actualsQuery.data.items}
        getRowKey={(row) => row.id}
        emptyTitle="実績はありません"
        emptyDescription="条件に一致する実績データは見つかりませんでした。"
      />

      <PaginationBar
        page={page}
        total={actualsQuery.data.total}
        limit={actualsQuery.data.limit}
        onPrevious={() => setPage((value) => Math.max(0, value - 1))}
        onNext={() => setPage((value) => value + 1)}
      />
    </div>
  );
}