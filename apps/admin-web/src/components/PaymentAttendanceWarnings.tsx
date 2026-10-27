import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getAttendanceNotes } from "../lib/attendanceNotesApi";
import "./paymentAttendanceWarnings.css";

/** 支払額とは独立した注意事項。PDFや確定額を書き換えない。 */
export function PaymentAttendanceWarnings({ periodKey, workerId }: { periodKey: string; workerId?: string }) {
  const [offset, setOffset] = useState(0);
  const query = useQuery({ queryKey: ["attendance-notes", "payment", periodKey, workerId, offset],
    queryFn: () => getAttendanceNotes({ period_key: periodKey, worker_id: workerId, offset }) });
  if (query.isPending) return <p role="status">支払の注意事項を確認中...</p>;
  if (query.isError) return <div role="alert"><p>注意事項を取得できません。注意事項なしとは判断せず、再読み込みしてください。</p><button type="button" className="secondary-button" onClick={() => query.refetch()}>再読み込み</button></div>;
  return <section className="card" style={{ padding: "1rem", border: "2px solid #b7791f" }} aria-label="支払の注意事項">
    <strong>{query.data.total ? `注意事項があります（${query.data.total}件）` : "対象月の遅刻・キャンセル記録はありません"}</strong>
    <p>対象月の稼働日について、金額を確定する前に確認してください。金額への自動反映は行いません。</p>
    {query.data.items.map(note => <div key={note.id} style={{ borderTop: "1px solid var(--color-border, #d0d5dd)", padding: "0.75rem 0" }}>
      <strong>{note.work_date}／{note.project_name}／{note.worker_name}：{note.summary}</strong>
      <div>{note.payment_note}</div><div style={{ whiteSpace: "pre-wrap" }}>理由：{note.reason}</div>
      <small>報告者：{note.reported_by}／記録者：{note.actor_name}</small>
    </div>)}
    {query.data.total > 50 && <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
      <button type="button" className="secondary-button" disabled={offset === 0} onClick={() => setOffset(offset - 50)}>前の50件</button>
      <span>{offset + 1}〜{Math.min(offset + 50, query.data.total)}／{query.data.total}件</span>
      <button type="button" className="secondary-button" disabled={offset + 50 >= query.data.total} onClick={() => setOffset(offset + 50)}>次の50件</button>
    </div>}
  </section>;
}
