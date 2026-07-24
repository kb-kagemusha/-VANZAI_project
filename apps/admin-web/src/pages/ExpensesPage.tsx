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
import { ApiError, approveExpense, downloadExpenseReceipt, getExpenses, rejectExpense } from "../lib/api/client";
import { currentMonthInput, formatCurrency, formatDate, formatDateTime, periodKeyToDateRange, toPeriodKey } from "../lib/formatters";

const PAGE_SIZE = 20;

export function ExpensesPage() {
  const [monthValue, setMonthValue] = useState(currentMonthInput());
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(0);
  const [actionError, setActionError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [rejectReasons, setRejectReasons] = useState<Record<string, string>>({});
  const periodKey = toPeriodKey(monthValue);
  const { from: expenseDateFrom, to: expenseDateTo } = periodKeyToDateRange(periodKey);
  const queryClient = useQueryClient();

  const expensesQuery = useQuery({
    queryKey: ["expenses", periodKey, status, category, page],
    queryFn: () =>
      getExpenses({
        status: status || undefined,
        category: category || undefined,
        expense_date_from: expenseDateFrom,
        expense_date_to: expenseDateTo,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
  });

  const approveMutation = useMutation({
    mutationFn: (expenseId: string) => approveExpense(expenseId),
    onSuccess: async () => {
      setActionError("");
      setActionMessage("経費を承認しました。");
      await queryClient.invalidateQueries({ queryKey: ["expenses"] });
    },
    onError: (error) => {
      setActionMessage("");
      setActionError(error instanceof ApiError ? error.message : "経費承認に失敗しました。");
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ expenseId, rejectReason }: { expenseId: string; rejectReason: string }) => rejectExpense(expenseId, rejectReason),
    onSuccess: async (_, variables) => {
      setActionError("");
      setActionMessage("経費を却下しました。");
      setRejectReasons((current) => ({ ...current, [variables.expenseId]: "" }));
      await queryClient.invalidateQueries({ queryKey: ["expenses"] });
    },
    onError: (error) => {
      setActionMessage("");
      setActionError(error instanceof ApiError ? error.message : "経費却下に失敗しました。");
    },
  });

  if (expensesQuery.isLoading) {
    return <LoadingOverlay label="経費一覧を読み込み中..." />;
  }

  if (expensesQuery.error instanceof ApiError && expensesQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (expensesQuery.isError || !expensesQuery.data) {
    return <ErrorState title="経費一覧の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  return (
    <div className="page-stack">
      <PageHeader title="経費一覧" description="経費申請、承認状況、証憑有無を対象月ごとに確認します。" />
      {actionError ? <p style={{ margin: 0, color: "var(--color-danger, #b42318)" }}>{actionError}</p> : null}
      {actionMessage ? <p style={{ margin: 0, color: "var(--color-success, #027a48)" }}>{actionMessage}</p> : null}
      <FilterBar>
        <label>
          対象月
          <input type="month" value={monthValue} onChange={(event) => { setMonthValue(event.target.value); setPage(0); }} />
        </label>
        <label>
          ステータス
          <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(0); }}>
            <option value="">すべて</option>
            <option value="pending">保留</option>
            <option value="approved">承認済み</option>
            <option value="rejected">却下</option>
          </select>
        </label>
        <label>
          カテゴリ
          <input value={category} onChange={(event) => { setCategory(event.target.value); setPage(0); }} placeholder="交通費、資材など" />
        </label>
      </FilterBar>

      <DataTable
        columns={[
          { key: "date", header: "日付", render: (row) => formatDate(row.expense_date) },
          { key: "project", header: "案件", render: (row) => row.project_name },
          { key: "worker", header: "稼働者", render: (row) => row.worker_name },
          { key: "category", header: "カテゴリ", render: (row) => row.category },
          { key: "amount", header: "金額", render: (row) => formatCurrency(row.amount) },
          { key: "status", header: "状態", render: (row) => <StatusBadge value={row.status} /> },
          { key: "approvedBy", header: "承認者", render: (row) => row.approved_by || "-" },
          { key: "approvedAt", header: "承認日時", render: (row) => formatDateTime(row.approved_at) },
          { key: "rejectReason", header: "却下理由", render: (row) => row.reject_reason || "-" },
          { key: "receipt", header: "証憑", render: (row) => (row.has_receipt ? "あり" : "なし") },
          {
            key: "actions",
            header: "操作",
            render: (row) => (
              <div style={{ display: "grid", gap: "0.4rem", minWidth: "14rem" }}>
                <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                  {row.status === "pending" ? (
                    <button
                      type="button"
                      onClick={() => approveMutation.mutate(row.id)}
                      disabled={approveMutation.isPending}
                    >
                      承認
                    </button>
                  ) : null}
                  {row.has_receipt ? (
                    <button
                      type="button"
                      onClick={() => {
                        void downloadExpenseReceipt(row.id).catch((error: unknown) => {
                          setActionMessage("");
                          setActionError(error instanceof ApiError ? error.message : "領収書のダウンロードに失敗しました。");
                        });
                      }}
                    >
                      領収書
                    </button>
                  ) : null}
                </div>
                {row.status === "pending" ? (
                  <>
                    <input
                      type="text"
                      value={rejectReasons[row.id] || ""}
                      onChange={(event) => setRejectReasons((current) => ({ ...current, [row.id]: event.target.value }))}
                      placeholder="却下理由を入力"
                    />
                    <button
                      type="button"
                      onClick={() => rejectMutation.mutate({ expenseId: row.id, rejectReason: rejectReasons[row.id] || "" })}
                      disabled={rejectMutation.isPending || !(rejectReasons[row.id] || "").trim()}
                    >
                      却下
                    </button>
                  </>
                ) : null}
              </div>
            ),
          },
        ]}
        rows={expensesQuery.data.items}
        getRowKey={(row) => row.id}
        emptyTitle="経費はありません"
        emptyDescription="条件に一致する経費データは見つかりませんでした。"
      />

      <PaginationBar
        page={page}
        total={expensesQuery.data.total}
        limit={expensesQuery.data.limit}
        onPrevious={() => setPage((value) => Math.max(0, value - 1))}
        onNext={() => setPage((value) => value + 1)}
      />
    </div>
  );
}