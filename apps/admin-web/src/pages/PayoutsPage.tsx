import { Navigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { PaginationBar } from "../components/PaginationBar";
import { StatusBadge } from "../components/StatusBadge";
import { ApiError, confirmPayout, generatePayout, getAssignments, getPayouts, getProjects } from "../lib/api/client";
import { currentMonthInput, formatCurrency, formatDateTime, formatPayeeType, toPeriodKey } from "../lib/formatters";

const PAGE_SIZE = 20;

export function PayoutsPage() {
  const [monthValue, setMonthValue] = useState(currentMonthInput());
  const [status, setStatus] = useState("");
  const [sortBy, setSortBy] = useState("approved_at");
  const [sortOrder, setSortOrder] = useState("desc");
  const [page, setPage] = useState(0);
  const [genProjectId, setGenProjectId] = useState("");
  const [genWorkerId, setGenWorkerId] = useState("");
  const [genError, setGenError] = useState("");
  const periodKey = toPeriodKey(monthValue);
  const queryClient = useQueryClient();

  const payoutsQuery = useQuery({
    queryKey: ["payouts", periodKey, status, sortBy, sortOrder, page],
    queryFn: () =>
      getPayouts({
        period_key: periodKey,
        status: status || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
  });

  const projectsQuery = useQuery({
    queryKey: ["projects-all"],
    queryFn: () => getProjects({ limit: 200 }),
  });

  const assignmentsQuery = useQuery({
    queryKey: ["assignments-gen", genProjectId],
    queryFn: () => getAssignments({ project_id: genProjectId, limit: 200 }),
    enabled: !!genProjectId,
  });

  const generateMutation = useMutation({
    mutationFn: () => generatePayout(genProjectId, genWorkerId, periodKey),
    onSuccess: () => {
      setGenError("");
      void queryClient.invalidateQueries({ queryKey: ["payouts"] });
    },
    onError: (err: unknown) => {
      setGenError(err instanceof ApiError ? err.message : "支払明細の生成に失敗しました");
    },
  });

  const confirmMutation = useMutation({
    mutationFn: (payoutId: string) => confirmPayout(payoutId),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["payouts"] }); },
    onError: () => { /* 将来対応 */ },
  });

  // 稼働者のユニーク一覧
  const workerOptions = Array.from(
    new Map((assignmentsQuery.data?.items ?? []).map((a) => [a.worker_id, a.worker_name])).entries(),
  );

  if (payoutsQuery.isLoading) {
    return <LoadingOverlay label="支払一覧を読み込み中..." />;
  }

  if (payoutsQuery.error instanceof ApiError && payoutsQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (payoutsQuery.isError || !payoutsQuery.data) {
    return <ErrorState title="支払一覧の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  return (
    <div className="page-stack">
      <PageHeader title="支払一覧" description="支払明細の相手先、版、承認・支払日時を参照します。" />

      {/* 支払明細生成フォーム */}
      <section className="card" style={{ padding: "1rem", display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "flex-end" }}>
        <strong style={{ width: "100%" }}>支払明細を生成</strong>
        <label>
          案件
          <select value={genProjectId} onChange={(e) => { setGenProjectId(e.target.value); setGenWorkerId(""); }}>
            <option value="">案件を選択</option>
            {(projectsQuery.data?.items ?? []).map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </label>
        <label>
          稼働者
          <select value={genWorkerId} onChange={(e) => setGenWorkerId(e.target.value)} disabled={!genProjectId}>
            <option value="">稼働者を選択</option>
            {workerOptions.map(([id, name]) => (
              <option key={id} value={id}>{name}</option>
            ))}
          </select>
        </label>
        <label>
          対象月
          <input type="month" value={monthValue} onChange={(e) => { setMonthValue(e.target.value); setPage(0); }} />
        </label>
        <button
          onClick={() => generateMutation.mutate()}
          disabled={!genProjectId || !genWorkerId || generateMutation.isPending}
        >
          {generateMutation.isPending ? "生成中..." : "支払明細生成"}
        </button>
        {genError && <span style={{ color: "var(--color-danger, red)", fontSize: "0.875rem" }}>{genError}</span>}
        {generateMutation.isSuccess && <span style={{ color: "green", fontSize: "0.875rem" }}>生成しました</span>}
      </section>

      <FilterBar>
        <label>
          対象月
          <input type="month" value={monthValue} onChange={(event) => { setMonthValue(event.target.value); setPage(0); }} />
        </label>
        <label>
          ステータス
          <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(0); }}>
            <option value="">すべて</option>
            <option value="preparing">準備中</option>
            <option value="approved">承認済み</option>
            <option value="paid">支払済み</option>
          </select>
        </label>
        <label>
          ソート
          <select value={sortBy} onChange={(event) => { setSortBy(event.target.value); setPage(0); }}>
            <option value="approved_at">承認日時</option>
            <option value="paid_at">支払日時</option>
            <option value="payee_name">支払先名</option>
            <option value="total_amount">合計金額</option>
            <option value="version">版</option>
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
          { key: "number", header: "支払番号", render: (row) => row.payout_number },
          { key: "payee", header: "支払先", render: (row) => row.payee_name },
          { key: "type", header: "種別", render: (row) => formatPayeeType(row.payee_type) },
          { key: "project", header: "案件", render: (row) => row.project_name || "-" },
          { key: "period", header: "対象月", render: (row) => row.period_key },
          { key: "version", header: "版", render: (row) => row.version },
          { key: "status", header: "状態", render: (row) => <StatusBadge value={row.status} /> },
          { key: "amount", header: "合計", render: (row) => formatCurrency(row.total_amount) },
          { key: "approved", header: "承認日時", render: (row) => formatDateTime(row.approved_at) },
          { key: "paid", header: "支払日時", render: (row) => formatDateTime(row.paid_at) },
          {
            key: "actions",
            header: "操作",
            render: (row) =>
              row.status === "preparing" ? (
                <button
                  onClick={() => confirmMutation.mutate(row.id)}
                  disabled={confirmMutation.isPending}
                  style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}
                >
                  確定
                </button>
              ) : null,
          },
        ]}
        rows={payoutsQuery.data.items}
        getRowKey={(row) => row.id}
        emptyTitle="支払明細はありません"
        emptyDescription="条件に一致する支払明細は見つかりませんでした。"
      />

      <PaginationBar
        page={page}
        total={payoutsQuery.data.total}
        limit={payoutsQuery.data.limit}
        onPrevious={() => setPage((value) => Math.max(0, value - 1))}
        onNext={() => setPage((value) => value + 1)}
      />
    </div>
  );
}