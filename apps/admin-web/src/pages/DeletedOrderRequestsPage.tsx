/**
 * 一覧から外した発注依頼書。行は残し、通常の一覧には出さない。
 * 管理者のプロフィールからのみ開く。
 */
import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { ApiError, listDeletedOrderRequests } from "../lib/api/client";
import { siteLabelForList } from "../lib/orderRequestFormat";

function messageOf(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "処理に失敗しました";
}

function formatWhen(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day} ${hour}:${minute}`;
}

export function DeletedOrderRequestsPage() {
  const listQuery = useQuery({
    queryKey: ["order-requests-deleted"],
    queryFn: () => listDeletedOrderRequests({ limit: 100, offset: 0 }),
  });

  return (
    <section>
      <PageHeader
        eyebrow="管理者"
        title="削除済み案件一覧"
        description="発注依頼書の一覧から外した案件です。データは残っています。このページは、管理者のプロフィールからのみ開けます。"
      />
      {listQuery.isLoading ? <LoadingOverlay /> : null}
      {listQuery.isError ? <ErrorState title="一覧を取得できませんでした" description={messageOf(listQuery.error)} /> : null}
      <section className="order-list-frame">
        <div className="order-list-table">
          <table className="data-table">
            <thead>
              <tr>
                <th>文書番号</th>
                <th>案件名</th>
                <th>区分</th>
                <th>状態</th>
                <th>日付</th>
                <th>外した人</th>
                <th>外した日時</th>
              </tr>
            </thead>
            <tbody>
              {(listQuery.data?.items ?? []).map((item) => (
                <tr key={item.version_id}>
                  <td>{item.document_number}</td>
                  <td className="order-cell-multiline">{siteLabelForList(item.project_name)}</td>
                  <td>{(item.change_documents ?? []).length > 0 ? "変更" : item.kind === "test" ? "テスト" : "正式"}</td>
                  <td>{item.status === "draft" ? "下書き" : item.status === "confirmed" ? "確定" : "取消"}</td>
                  <td className="order-cell-multiline">{item.work_date_label}</td>
                  <td>{item.deleted_by_name ?? "—"}</td>
                  <td>{formatWhen(item.deleted_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {listQuery.data && listQuery.data.items.length === 0 ? (
            <EmptyState title="削除済みはありません" description="一覧から外した発注依頼書がここに出ます。" />
          ) : null}
        </div>
      </section>
    </section>
  );
}
