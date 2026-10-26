import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { DataTable } from "../components/DataTable";
import { PaginationBar } from "../components/PaginationBar";
import { PageHeader } from "../components/PageHeader";
import { LineRegistrationReviewModal } from "../components/LineRegistrationReviewModal";
import { OperatorRegistrationReviewDialog } from "../components/OperatorRegistrationReviewDialog";
import { useAuth } from "../lib/auth/auth-context";
import { getRegistrationRequests } from "../lib/api/client";
import { formatDateTime } from "../lib/formatters";
const PAGE_SIZE = 30;

function LineRegistrationInbox({ canReview }: { canReview: boolean }) {
  const [page, setPage] = useState(0);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [requestType, setRequestType] = useState("worker");
  const requestsQuery = useQuery({
    queryKey: ["registration-requests", "worker-line-pending", page],
    queryFn: () => getRegistrationRequests({
      status: "pending",
      line_only: true,
      sort_by: "submitted_at",
      sort_order: "desc",
      offset: page * PAGE_SIZE,
      limit: PAGE_SIZE,
    }),
    refetchInterval: 30_000,
  });
  useEffect(() => {
    if (requestsQuery.data && page > 0 && requestsQuery.data.total <= page * PAGE_SIZE) {
      setPage(Math.max(0, Math.ceil(requestsQuery.data.total / PAGE_SIZE) - 1));
    }
  }, [requestsQuery.data, page]);

  return (
    <section className="card" style={{ padding: "0.9rem 1rem", display: "grid", gap: "0.75rem" }}>
      <div style={{ display: "flex", gap: "0.75rem", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>登録・確認待ち{requestsQuery.data ? `（${requestsQuery.data.total}件）` : ""}</h2>
        <button type="button" className="btn btn-ghost" disabled={requestsQuery.isFetching} onClick={() => { setPage(0); void requestsQuery.refetch(); }}>
          申請を更新
        </button>
      </div>
      <p style={{ margin: 0 }}>区分と申請内容・反映先を確認してください。承認すると対象の登録一覧へ反映されます。</p>
      {requestsQuery.isLoading ? <p>登録申請を読み込み中...</p> : null}
      {requestsQuery.isError ? <p className="form-error">LINE登録申請を取得できませんでした。申請を更新してください。</p> : null}
      {requestsQuery.data ? (
        <>
          <DataTable
            rows={requestsQuery.data.items}
            getRowKey={(row) => row.id}
            columns={[
              { key: "category", header: "区分", render: (row) => <span className={`status-badge ${row.request_type === "operator_staff" ? "attention" : "active"}`}>{row.request_type === "operator_staff" ? "運営スタッフ" : "稼働者"}</span> },
              { key: "name", header: "申請者", render: (row) => row.summary_name || "氏名の変更なし" },
              { key: "submitted", header: "申請日時", render: (row) => formatDateTime(row.submitted_at) },
              { key: "status", header: "状態", render: () => "管理者確認待ち" },
              { key: "review", header: "操作", render: (row) => (
                canReview ? <button type="button" className="btn btn-primary" onClick={() => { setRequestType(row.request_type); setRequestId(row.id); }}>内容を確認・反映</button> : "管理者が承認します"
              ) },
            ]}
            emptyTitle="LINEの確認待ち申請はありません"
            emptyDescription="送信済みの申請はここに表示されます。承認済みの方は稼働者・運営スタッフそれぞれの一覧で確認してください。"
          />
          <PaginationBar page={page} limit={PAGE_SIZE} total={requestsQuery.data.total} onPrevious={() => setPage((current) => Math.max(0, current - 1))} onNext={() => setPage((current) => current + 1)} />
        </>
      ) : null}
      {requestId ? (
        requestType === "operator_staff" ? <OperatorRegistrationReviewDialog requestId={requestId} onClose={() => setRequestId(null)} /> : <LineRegistrationReviewModal requestId={requestId} onClose={() => setRequestId(null)} />
      ) : null}
    </section>
  );
}

export function RegistrationPendingPage() {
  const { user } = useAuth();
  return <div className="page-stack">
    <PageHeader title="登録確認待ち" eyebrow="マスタ" description="登録・変更申請を新しい順に表示します。区分で登録先を確認し、内容を審査してください。" />
    <LineRegistrationInbox canReview={user?.role === "admin"} />
  </div>;
}
