import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../lib/api/client";
import { confirmApp } from "../lib/appDialog";
import { FormDialog } from "./FormDialog";
import { PaginationBar } from "./PaginationBar";
import "../styles/orderChangeDelivery.css";

type Person = { delivery_id: string; worker_name: string; send_status: string; line_linked: boolean; can_send: boolean };
type Group = { version_id: string; document_number: string; project_name: string; kind: string; version_no: number; recipients: Person[] };
type Result = { items: Group[]; total: number; pending_people: number; line_send_available: boolean };
const labels: Record<string, string> = { unsent: "未送信", failed: "送信失敗", unknown: "結果不明・要確認", processing: "送信処理中" };

export function OrderChangeDeliveryNotice({ kind, canWrite, onOpen }: { kind: string; canWrite: boolean; onOpen: (id: string) => void }) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false), [page, setPage] = useState(0);
  const [busy, setBusy] = useState<string | null>(null), [message, setMessage] = useState("");
  const result = useQuery({ queryKey: ["order-requests", "change-delivery-pending", kind, page],
    queryFn: () => apiFetch<Result>("/api/order-requests/change-delivery-pending", undefined, { kind, limit: 10, offset: page * 10 }),
    refetchInterval: 30_000, refetchOnWindowFocus: true });
  const data = result.data;
  useEffect(() => { if (data) setPage(p => Math.min(p, Math.max(0, Math.ceil(data.total / 10) - 1))); }, [data]);
  async function send(group: Group, person: Person) {
    if (busy) return;
    const yes = await confirmApp({ title: "変更版をLINEで送付", message: `${person.worker_name}さんに「${group.project_name}」の第${group.version_no}版を送付します。`, confirmLabel: "送付する" });
    if (!yes) return;
    setBusy(person.delivery_id); setMessage("");
    try {
      const sent = await apiFetch<{ send_status: string }>(`/api/order-requests/change-delivery-pending/${person.delivery_id}/send`, { method: "POST" });
      setMessage(sent.send_status === "accepted" ? `${person.worker_name}さんへの送信を受け付けました。本人の返事はまだです。` : `${person.worker_name}さん：${labels[sent.send_status] ?? sent.send_status}。状態を確認してください。`);
      await client.invalidateQueries({ queryKey: ["order-requests"] });
      await client.invalidateQueries({ queryKey: ["order-request-replies"] });
      await client.invalidateQueries({ queryKey: ["order-request"] });
    } catch (error) { setMessage(error instanceof Error ? error.message : "送信できませんでした"); }
    finally { setBusy(null); }
  }
  if (result.isError) return <p className="form-error" role="alert">変更版の送付待ちを取得できませんでした。<button className="btn btn-ghost btn-sm" onClick={() => void result.refetch()}>再取得</button></p>;
  if (!data?.pending_people && !open) return null;
  return <>
    {Boolean(data?.pending_people) && <aside className="order-change-delivery-notice" aria-label="変更版の送付待ち">
      <div><strong>変更版の送付待ち・要確認：{data?.pending_people}人（{data?.total}件）</strong>
        <p>旧版を受諾した人への変更版の送信が完了していません。</p></div>
      <button className="btn btn-warning" type="button" onClick={() => { setPage(0); setOpen(true); }}>対象者を確認・送付</button>
    </aside>}
    <FormDialog open={open} title="変更版の送付待ち・要確認" busy={Boolean(busy)} onClose={() => setOpen(false)}>
      <p>未送信・送信失敗はここから送付できます。結果不明・送信処理中は、重複を避けるためここから再送しません。</p>
      {message && <p role="status">{message}</p>}
      {result.isFetching && <p>更新しています…</p>}
      {!data?.pending_people && <p>変更版の送付待ちはありません。</p>}
      {(data?.items ?? []).map(group => <section key={group.version_id} className="order-change-delivery-group">
        <div className="order-change-delivery-heading"><strong>{group.kind === "test" ? "【テスト】 " : ""}{group.project_name}（第{group.version_no}版）</strong>
          <button type="button" className="btn btn-ghost btn-sm" disabled={Boolean(busy)} onClick={() => { setOpen(false); onOpen(group.version_id); }}>{group.document_number}を確認</button></div>
        <ul>{group.recipients.map(person => <li key={person.delivery_id}>
          <span>{person.worker_name}</span><span>{labels[person.send_status] ?? person.send_status}{!person.line_linked ? "・LINE未連携" : ""}</span>
          {canWrite && <button type="button" className="btn btn-line-blue btn-sm" disabled={Boolean(busy) || !person.can_send || !data?.line_send_available} onClick={() => void send(group, person)}>{busy === person.delivery_id ? "送信中…" : "変更版を送付"}</button>}
        </li>)}</ul>
      </section>)}
      {data && !data.line_send_available && <p>サーバーのLINE設定がないため送付できません。</p>}
      <PaginationBar page={page} limit={10} total={data?.total ?? 0} onPrevious={() => setPage(p => Math.max(0, p - 1))} onNext={() => setPage(p => p + 1)} />
    </FormDialog>
  </>;
}
