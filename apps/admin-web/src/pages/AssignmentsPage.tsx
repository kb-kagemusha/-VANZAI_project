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
import { ApiError, getAssignments } from "../lib/api/client";
import { currentMonthInput, formatCurrency, formatDate, toPeriodKey } from "../lib/formatters";

const PAGE_SIZE = 20;

export function AssignmentsPage() {
  const [monthValue, setMonthValue] = useState(currentMonthInput());
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const periodKey = toPeriodKey(monthValue);
  const workDateFrom = `${periodKey.slice(0, 4)}-${periodKey.slice(4, 6)}-01`;
  const workDateTo = `${periodKey.slice(0, 4)}-${periodKey.slice(4, 6)}-31`;

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

  return (
    <div className="page-stack">
      <PageHeader title="アサイン一覧" description="予定、役割、ロック単価を一覧で確認します。" />
      <FilterBar>
        <label>
          対象月
          <input type="month" value={monthValue} onChange={(event) => { setMonthValue(event.target.value); setPage(0); }} />
        </label>
        <label>
          ステータス
          <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(0); }}>
            <option value="">すべて</option>
            <option value="confirmed">確定</option>
            <option value="pending">保留</option>
            <option value="canceled">取消</option>
          </select>
        </label>
      </FilterBar>

      <DataTable
        columns={[
          { key: "date", header: "日付", render: (row) => formatDate(row.work_date) },
          { key: "project", header: "案件", render: (row) => row.project_name },
          { key: "shift", header: "シフト", render: (row) => row.shift_label || "-" },
          { key: "worker", header: "稼働者", render: (row) => row.worker_name },
          { key: "role", header: "役割", render: (row) => row.role_name },
          { key: "status", header: "状態", render: (row) => <StatusBadge value={row.status} /> },
          { key: "sales", header: "売上単価", render: (row) => formatCurrency(row.locked_price_sales) },
          { key: "outsource", header: "外注単価", render: (row) => formatCurrency(row.locked_price_outsource) },
        ]}
        rows={assignmentsQuery.data.items}
        getRowKey={(row) => row.id}
        emptyTitle="アサインはありません"
        emptyDescription="条件に一致するアサインデータは見つかりませんでした。"
      />

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