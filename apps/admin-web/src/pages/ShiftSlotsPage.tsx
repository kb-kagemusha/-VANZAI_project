import { Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { PaginationBar } from "../components/PaginationBar";
import { ApiError, getShiftSlots } from "../lib/api/client";
import { currentMonthInput, formatDate, toPeriodKey } from "../lib/formatters";

const PAGE_SIZE = 20;

export function ShiftSlotsPage() {
  const [monthValue, setMonthValue] = useState(currentMonthInput());
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("work_date");
  const [sortOrder, setSortOrder] = useState("desc");
  const [page, setPage] = useState(0);
  const periodKey = toPeriodKey(monthValue);
  const workDateFrom = `${periodKey.slice(0, 4)}-${periodKey.slice(4, 6)}-01`;
  const workDateTo = `${periodKey.slice(0, 4)}-${periodKey.slice(4, 6)}-31`;

  const shiftSlotsQuery = useQuery({
    queryKey: ["shift-slots", periodKey, search, sortBy, sortOrder, page],
    queryFn: () =>
      getShiftSlots({
        search: search || undefined,
        work_date_from: workDateFrom,
        work_date_to: workDateTo,
        sort_by: sortBy,
        sort_order: sortOrder,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
  });

  if (shiftSlotsQuery.isLoading) {
    return <LoadingOverlay label="シフト枠一覧を読み込み中..." />;
  }

  if (shiftSlotsQuery.error instanceof ApiError && shiftSlotsQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (shiftSlotsQuery.isError || !shiftSlotsQuery.data) {
    return <ErrorState title="シフト枠一覧の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  return (
    <div className="page-stack">
      <PageHeader title="シフト枠一覧" description="対象月のシフト枠、必要人数、充足状況を確認します。" />
      <FilterBar>
        <label>
          対象月
          <input type="month" value={monthValue} onChange={(event) => { setMonthValue(event.target.value); setPage(0); }} />
        </label>
        <label>
          検索
          <input value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder="案件名、シフト名" />
        </label>
        <label>
          ソート
          <select value={sortBy} onChange={(event) => { setSortBy(event.target.value); setPage(0); }}>
            <option value="work_date">作業日</option>
            <option value="project_name">案件名</option>
            <option value="required_count">必要人数</option>
            <option value="assigned_count">確定人数</option>
          </select>
        </label>
        <label>
          順序
          <select value={sortOrder} onChange={(event) => { setSortOrder(event.target.value); setPage(0); }}>
            <option value="desc">降順</option>
            <option value="asc">昇順</option>
          </select>
        </label>
      </FilterBar>

      <DataTable
        columns={[
          { key: "project", header: "案件", render: (row) => row.project_name },
          { key: "date", header: "日付", render: (row) => formatDate(row.work_date) },
          { key: "start", header: "開始", render: (row) => row.start_time || "-" },
          { key: "end", header: "終了", render: (row) => row.end_time || "-" },
          { key: "label", header: "シフト", render: (row) => row.shift_label || "-" },
          { key: "required", header: "必要人数", render: (row) => row.required_count },
          { key: "assigned", header: "確定人数", render: (row) => row.assigned_count },
          { key: "notes", header: "備考", render: (row) => row.notes || "-" },
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