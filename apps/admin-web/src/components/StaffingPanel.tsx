import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../lib/api/client";
import { FormDialog } from "./FormDialog";
import "../styles/staffing.css";

type Day = { date: string; capacity: number; confirmed: number; family_confirmed?: number; confirmed_ids: string[]; closed: boolean };
type Person = { worker_id: string; name: string; accepted_dates: string[]; offered_dates: string[]; ack_status: string; send_status?: string; available: boolean };
type Staffing = { enabled: boolean; revision: number; is_test: boolean; is_replacement?: boolean; notifications_enabled?: boolean; days: Day[]; people: Person[]; notices: { status: string; worker_id?: string; date?: string; kind?: string }[] };
export type StaffingRequester = <T>(path: string, init?: RequestInit) => Promise<T>;

/** All staffing input remains inside a modal; viewing a request never sends LINE. */
export function StaffingPanel({ versionId, canWrite, request = apiFetch }: { versionId: string; canWrite: boolean; request?: StaffingRequester }) {
  const [open, setOpen] = useState(false);
  return <><button type="button" className="btn btn-line-blue" onClick={() => setOpen(true)}>参加者・日別人数を確認</button>
    {open ? <StaffingDialog versionId={versionId} canWrite={canWrite} request={request} onClose={() => setOpen(false)} /> : null}</>;
}

function StaffingDialog({ versionId, canWrite, request, onClose }: { versionId: string; canWrite: boolean; request: StaffingRequester; onClose: () => void }) {
  const cache = useQueryClient();
  const endpoint = `/api/order-staffing/${versionId}`;
  const query = useQuery({ queryKey: ["staffing", versionId], queryFn: () => request<Staffing>(endpoint) });
  const [capacities, setCapacities] = useState<Record<string, number>>({});
  const [selected, setSelected] = useState<Record<string, string[]>>({});
  const [closeDates, setCloseDates] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [review, setReview] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    if (!query.data) return;
    setCapacities(Object.fromEntries(query.data.days.map(d => [d.date, d.capacity])));
    setSelected(Object.fromEntries(query.data.days.map(d => [d.date, d.confirmed_ids])));
    setCloseDates([]); setReview(false);
  }, [query.data]);
  const save = useMutation({
    mutationFn: (action: "limits" | "decisions" | "notices/send") => request(endpoint + "/" + action, {
      method: action === "limits" ? "PUT" : "POST",
      body: action === "notices/send" ? undefined : JSON.stringify(action === "limits" ? { capacities, revision: query.data?.revision } : {
        selected: Object.fromEntries(query.data!.days.filter(d => !d.closed).map(d => [d.date, selected[d.date] ?? []])),
        close_dates: closeDates, reason, revision: query.data?.revision,
      }),
    }),
    onSuccess: async (_result, action) => {
      setReview(false);
      setMessage(action === "limits" ? "上限人数を保存しました。" : action === "decisions" ? "参加者を確定しました。通知結果を下で確認してください。" : "通知の送信結果を更新しました。");
      await cache.invalidateQueries();
    },
  });
  const data = query.data;
  const dirty = data?.days.some(d => capacities[d.date] !== d.capacity);
  const failures = data?.notices.filter(n => ["failed", "pending"].includes(n.status)).length ?? 0;
  const newCount = data?.days.reduce((n,d) => n + (selected[d.date] ?? []).filter(id => !d.confirmed_ids.includes(id)).length, 0) ?? 0;
  const noticePreview = data?.days.filter(d => !d.closed).flatMap(day => {
    const chosen = selected[day.date] ?? [];
    const closing = closeDates.includes(day.date) || (day.capacity > 0 && chosen.length === day.capacity);
    return data.people.flatMap(person => {
      const kind = chosen.includes(person.worker_id) && !day.confirmed_ids.includes(person.worker_id) ? "confirmed"
        : closing && !chosen.includes(person.worker_id) && person.offered_dates.includes(day.date) && !["declined", "decline_pending"].includes(person.ack_status)
          && (["accepted", "unknown"].includes(person.send_status ?? "") || person.ack_status === "acked") ? "closed" : null;
      return kind && !data.notices.some(n => n.worker_id === person.worker_id && n.date === day.date && n.kind === kind)
        ? [{ date: day.date, name: person.name, kind }] : [];
    });
  }) ?? [];
  return <FormDialog open title="参加者の最終確定" onClose={onClose} busy={save.isPending}>
    <div className="staffing-form">
    {query.isLoading ? <p>読み込んでいます…</p> : null}
    {query.error || save.error ? <p role="alert">{(query.error ?? save.error)?.message ?? "操作に失敗しました。最新の状態を確認してください。"}</p> : null}
    {message ? <p role="status">{message}</p> : null}
    {data?.enabled ? <>
      <p>{data.is_test ? "【テスト】" : ""}参加可能の回答は未確定です。運営が選んだ方へ参加確定を通知します。</p>
      {data.is_test && data.notifications_enabled === false ? <p className="form-error">テスト通知はオフです。参加者の確定は保存し、LINE通知は省略します。</p> : null}
      <p>上限まで確定すると、その日の募集は終了し、見送り・未回答の方へお礼を通知します。参加不可の方には終了通知を送りません。</p>
      {data.days.map(day => <fieldset key={day.date} disabled={!canWrite || save.isPending || day.closed} style={{ marginBottom: 16, padding: 16, border: "1px solid var(--border-color, #aaa)", borderRadius: 8 }}>
        <legend>{day.date}　{day.closed ? "募集終了" : `確定 ${day.family_confirmed ?? day.confirmed}人`}</legend>
        <label>上限人数 <input type="number" disabled={data.is_replacement} min={day.family_confirmed ?? day.confirmed} step={1} value={capacities[day.date] ?? 0} style={{ width: 90 }} onChange={e => { setReview(false); setCapacities({ ...capacities, [day.date]: Number(e.target.value) }); }} /></label>
        <p>選択 {(selected[day.date] ?? []).length}人 / 上限 {day.capacity}人</p>
        {data.people.filter(p => p.offered_dates.includes(day.date)).map(p => {
          const confirmed = day.confirmed_ids.includes(p.worker_id);
          const available = p.available && p.accepted_dates.includes(day.date);
          return <label key={p.worker_id} style={{ display: "block", padding: "6px 0" }}><input type="checkbox" disabled={!available || confirmed || Boolean(dirty)} checked={(selected[day.date] ?? []).includes(p.worker_id)} onChange={e => {
            setReview(false);
            setSelected({ ...selected, [day.date]: e.target.checked ? [...(selected[day.date] ?? []), p.worker_id] : (selected[day.date] ?? []).filter(id => id !== p.worker_id) });
          }} /> {p.name}　{confirmed ? "参加確定" : available ? "参加可能（未確定）" : p.ack_status === "declined" ? "参加不可" : "回答待ち"}</label>;
        })}
        <label><input type="checkbox" checked={closeDates.includes(day.date)} onChange={e => { setReview(false); setCloseDates(e.target.checked ? [...closeDates, day.date] : closeDates.filter(d => d !== day.date)); }} />上限未達でも、この日の募集を終了する</label>
      </fieldset>)}
      {canWrite ? <>
        <button type="button" className="btn btn-line-blue" disabled={save.isPending || !dirty} onClick={() => save.mutate("limits")}>上限人数を保存</button>
        <label className="order-field staffing-reason">調整の記録・人数未達で終了する理由<textarea rows={2} value={reason} maxLength={1000} disabled={save.isPending} onChange={e => setReason(e.target.value)} /></label>
        {review ? <div role="status"><p>新たに {newCount}人日の参加を確定します。満員になる日・終了を選んだ日は募集を閉じ、通知を送ります。</p><p>通知予定 {noticePreview.length}件</p><ul>{noticePreview.map((n,i) => <li key={i}>{n.date}　{n.name}：{n.kind === "confirmed" ? "参加確定とお礼" : "募集終了とお礼"}</li>)}</ul><button type="button" className="btn create-button" disabled={save.isPending || Boolean(dirty)} onClick={() => save.mutate("decisions")}>この内容で確定・通知する</button><button type="button" className="btn btn-ghost" onClick={() => setReview(false)}>戻る</button></div> : <button type="button" className="btn create-button" disabled={save.isPending || Boolean(dirty) || (!newCount && !closeDates.length)} onClick={() => setReview(true)}>確定内容を確認</button>}
      </> : null}
      <p>通知：送信済み {data.notices.filter(n => n.status === "sent").length}件 ／ テスト停止などで送付省略 {data.notices.filter(n => ["skipped", "cancelled"].includes(n.status)).length}件 ／ 未送信・失敗 {failures}件</p>
      {failures > 0 && canWrite ? <button type="button" className="btn btn-line-blue" disabled={save.isPending} onClick={() => save.mutate("notices/send")}>未送信・失敗分を送る（最大20件）</button> : null}
    </> : null}
    </div>
  </FormDialog>;
}
