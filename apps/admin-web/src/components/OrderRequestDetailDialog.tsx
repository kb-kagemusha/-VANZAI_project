import { useQuery } from "@tanstack/react-query";
import { FormDialog } from "./FormDialog";
import { ErrorState } from "./ErrorState";
import { getOrderRequestVersion } from "../lib/api/client";

/** カレンダーの閲覧権限で、表示中の回答受付版を確認する。 */
export function OrderRequestDetailDialog({ versionId, onClose }: { versionId: string; onClose: () => void }) {
  const query = useQuery({ queryKey: ["order-request", versionId], queryFn: () => getOrderRequestVersion(versionId) });
  const detail = query.data;
  return <FormDialog open title={detail ? `発注依頼書 ${detail.document_number}（第${detail.version_no}版）` : "発注依頼書の詳細"} onClose={onClose}>
    {query.isLoading ? <p>読み込んでいます…</p> : null}
    {query.isError ? <ErrorState title="依頼書を読み込めませんでした" description="時間をおいて再度お試しください。" /> : null}
    {detail ? <>
      <p>稼働日：{detail.work_date_label}</p>
      <pre className="order-detail-body">{detail.body}</pre>
      <h4>送付先・返事</h4>
      <div className="order-draft-table"><table className="data-table"><thead><tr><th>送付先</th><th>返事</th></tr></thead><tbody>
        {detail.deliveries.map((row) => <tr key={row.id}><td>{row.worker_name_snapshot}</td><td>{({ acked: "受諾", declined: "辞退", decline_pending: "辞退理由待ち", unacked: "未回答" } as Record<string, string>)[row.ack_status] ?? row.ack_status}</td></tr>)}
      </tbody></table></div>
    </> : null}
  </FormDialog>;
}
