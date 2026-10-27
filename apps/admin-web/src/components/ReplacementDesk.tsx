import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../lib/api/client";
import { FormDialog } from "./FormDialog";
import { StaffingPanel, type StaffingRequester } from "./StaffingPanel";
import "../styles/staffing.css";

type Choice = { id: string; project_name: string };
type Open = { entries?: Choice[]; vacancyId?: string; reason?: string };
type Vacancy = { id: string; revision: number; status: string; date: string; worker_name: string; project_name: string; is_test: boolean; reason: string; source_active?: boolean; recruitment_version_id: string | null };
type Preview = { entry_id: string; date: string; worker_name: string; project_name: string; is_test: boolean; guard: string };
type Candidate = { id: string; name: string; availability: string | null; line_linked: boolean };

export function openReplacement(entries: Choice[], reason = "") {
  window.dispatchEvent(new CustomEvent<Open>("vanzai:replacement-open", { detail: { entries, reason } }));
}

export function ReplacementDesk({ day, canWrite, enabled = true, includeTest = true, request = apiFetch, onChanged }: {
  day: string; canWrite: boolean; enabled?: boolean; includeTest?: boolean; request?: StaffingRequester; onChanged?: () => void;
}) {
  const [open, setOpen] = useState<Open | null>(null);
  const query = useQuery({ queryKey: ["replacement-vacancies",day], enabled, queryFn: () => request<{ items: Vacancy[] }>(`/api/staffing-replacements?date=${day}`) });
  useEffect(() => {
    const handler = (event: Event) => { if (canWrite) setOpen((event as CustomEvent<Open>).detail); };
    window.addEventListener("vanzai:replacement-open", handler);
    return () => window.removeEventListener("vanzai:replacement-open", handler);
  }, [canWrite]);
  const items=(query.data?.items ?? []).filter(v=>includeTest || !v.is_test);
  return <>
    {enabled && (items.length || query.error) ? <section className="card staffing-vacancies"><h3>欠員・代替手配</h3>
      {query.error ? <p role="alert">欠員の記録を読み込めませんでした。</p> : null}
      {items.map(v => <div className="staffing-vacancy-row" key={v.id}><div><strong>{v.is_test ? "【テスト】" : ""}{v.project_name}</strong><p>{v.worker_name}さんの欠員：{({open:"未手配",recruiting:"代替者を募集中",filled:"代替者が確定"} as Record<string,string>)[v.status] ?? v.status}</p></div>
        <button type="button" className="btn btn-line-blue" onClick={() => setOpen({vacancyId:v.id})}>手配状況を確認</button></div>)}
    </section> : null}
    {open ? <ReplacementDialog initial={open} canWrite={canWrite} request={request} onClose={() => setOpen(null)} onChanged={onChanged} /> : null}
  </>;
}

const localInput = (value: Date) => new Intl.DateTimeFormat("sv-SE",{timeZone:"Asia/Tokyo",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).format(value).replace(" ","T");

function ReplacementDialog({ initial, canWrite, request, onClose, onChanged }: { initial: Open; canWrite: boolean; request: StaffingRequester; onClose: () => void; onChanged?: () => void }) {
  const cache=useQueryClient();
  const [entryId,setEntryId]=useState(initial.entries?.length === 1 ? initial.entries[0].id : "");
  const [vacancyId,setVacancyId]=useState(initial.vacancyId ?? "");
  const [reason,setReason]=useState(initial.reason ?? "");
  const [selected,setSelected]=useState<string[]>([]);
  const [deadline,setDeadline]=useState(localInput(new Date(Date.now()+3600000)));
  const [editingRecruit,setEditingRecruit]=useState(false);
  const [review,setReview]=useState(false);
  const [sendReview,setSendReview]=useState(false);
  const [message,setMessage]=useState("");
  const preview=useQuery({queryKey:["vacancy-preview",entryId],enabled:!vacancyId && !!entryId,queryFn:()=>request<Preview>(`/api/staffing-replacements/entries/${entryId}`),retry:false});
  const vacancy=useQuery({queryKey:["vacancy",vacancyId],enabled:!!vacancyId,queryFn:()=>request<Vacancy>(`/api/staffing-replacements/${vacancyId}`)});
  const candidates=useQuery({queryKey:["replacement-candidates",vacancyId],enabled:!!vacancyId && canWrite && (!vacancy.data?.recruitment_version_id || editingRecruit),queryFn:()=>request<{items:Candidate[]}>(`/api/staffing-replacements/${vacancyId}/candidates`)});
  const item=vacancy.data;
  const invitation=useQuery({queryKey:["replacement-invitation",vacancyId,item?.recruitment_version_id],enabled:!!item?.recruitment_version_id && sendReview,queryFn:()=>request<{body:string;notifications_enabled:boolean;recipients:{name:string;send_status:string;ack_status:string}[]}>(`/api/staffing-replacements/${vacancyId}/invitation`)});
  const save=useMutation({mutationFn:async(action:"create"|"recruit"|"send"|"cancel")=>{
    if(action === "create") {
      const result=await request<Vacancy>("/api/staffing-replacements",{method:"POST",body:JSON.stringify({entry_id:entryId,guard:preview.data?.guard,reason})});
      setVacancyId(result.id); cache.setQueryData(["vacancy",result.id],result);
      return "欠員を登録し、この日の予定から外しました。続けて候補者を選べます。";
    }
    const body=action === "recruit" ? {worker_ids:selected,deadline:new Date(`${deadline}+09:00`).toISOString(),revision:item?.revision}
      : action === "send" ? {version_id:item?.recruitment_version_id,revision:item?.revision} : {reason,revision:item?.revision};
    const result=await request<Vacancy | {sent:number;remaining:number;unknown:number}>(`/api/staffing-replacements/${vacancyId}/${action}`,{method:"POST",body:JSON.stringify(body)});
    if(action === "send" && "sent" in result) return `送信済み ${result.sent}件／未送信 ${result.remaining}件／応答不明 ${result.unknown}件。応答不明の方への重複送信は避け、記録を確認してください。`;
    if(action === "recruit") {setEditingRecruit(false);setReview(false);return "募集内容を保存しました。依頼書と送付先を確認してから送信してください。";}
    return "欠員を取り消し、元の予定を戻しました。";
  },onSuccess:async(text,action)=>{setMessage(text);await cache.invalidateQueries();onChanged?.();if(action === "cancel") onClose();}});
  return <FormDialog open title="欠員・代替人員の手配" busy={save.isPending} onClose={onClose}><div className="staffing-form">
    {message ? <p role="status">{message}</p> : null}
    {preview.error || vacancy.error || save.error ? <p role="alert">{(preview.error ?? vacancy.error ?? save.error)?.message}</p> : null}
    {!vacancyId ? <>
      <p>欠員にする案件・日付を確認します。他の日の予定や、元の回答・実績・金額は保持します。</p>
      {(initial.entries?.length ?? 0)>1 ? <fieldset><legend>対象の案件</legend>{initial.entries?.map(e=><label className="staffing-candidate" key={e.id}><input type="radio" name="vacancy-entry" checked={entryId === e.id} onChange={()=>setEntryId(e.id)} />{e.project_name}</label>)}</fieldset> : null}
      {preview.data ? <p><strong>{preview.data.is_test ? "【テスト】" : ""}{preview.data.project_name}</strong><br />{preview.data.date}　{preview.data.worker_name}さん</p> : null}
      <label className="order-field staffing-reason">欠員にする理由<textarea value={reason} maxLength={1000} onChange={e=>setReason(e.target.value)} /></label>
      <button type="button" className="btn create-button" disabled={!canWrite || !preview.data || !reason.trim() || save.isPending} onClick={()=>save.mutate("create")}>欠員として、この日の予定から外す</button>
    </> : item ? <>
      <p><strong>{item.is_test ? "【テスト】" : ""}{item.project_name}</strong><br />{item.date}　{item.worker_name}さんの欠員</p>
      <p>記録：{item.reason}</p>
      {item.source_active === false ? <p>元の案件は終了しています。手配は記録の確認のみです。</p> : null}
      {item.recruitment_version_id && item.source_active !== false ? <><StaffingPanel versionId={item.recruitment_version_id} canWrite={canWrite} request={request} />
        {item.status === "recruiting" && canWrite ? <><button type="button" className="btn btn-line-blue" onClick={()=>setSendReview(!sendReview)}>募集の内容・送付先を確認</button>
          {sendReview ? <>{invitation.error ? <p role="alert">募集内容を読み込めませんでした。</p> : null}{invitation.data ? <><pre className="staffing-invitation">{invitation.data.body}</pre><p>送付先：{invitation.data.recipients.map(p=>p.name).join("、")}</p><p>未送信 {invitation.data.recipients.filter(p=>!["accepted","unknown"].includes(p.send_status) && p.ack_status === "unacked").length}名。最大20名ずつ送信します。</p>{!invitation.data.notifications_enabled ? <p className="form-error">テスト通知はオフです。起床状況の通知設定を有効にするまで、募集のLINEは送れません。</p> : null}<button type="button" className="btn create-button" disabled={save.isPending || !invitation.data.notifications_enabled} onClick={()=>save.mutate("send")}>この内容で募集のLINEを送る</button></> : <p>確認しています…</p>}</> : null}
          <button type="button" className="btn btn-line-blue" onClick={()=>setEditingRecruit(!editingRecruit)}>募集終了後に、候補を選び直す</button></> : null}
      </> : null}
      {canWrite && item.source_active !== false && ["open","recruiting"].includes(item.status) && (!item.recruitment_version_id || editingRecruit) ? <>
        <p>同日に別案件の確定予定がある方と、出勤不可の方を除いています。可否未登録の方は表示しているので、選ぶ際に確認してください。</p>
        {candidates.error ? <p role="alert">候補者を取得できませんでした。</p> : null}
        <fieldset><legend>打診する方（必要人数1名）</legend>{candidates.data?.items.map(person=><label className="staffing-candidate" key={person.id}><input type="checkbox" checked={selected.includes(person.id)} disabled={!person.line_linked || save.isPending} onChange={e=>{setReview(false);setSelected(e.target.checked?[...selected,person.id]:selected.filter(id=>id!==person.id));}} />{person.name}　{({available_all_day:"終日可",available_after_15:"15時以降可",consult_required:"要相談",undecided:"未定"} as Record<string,string>)[person.availability ?? ""] ?? "可否未登録"}{!person.line_linked ? "（LINE未連携）" : ""}</label>)}</fieldset>
        <label className="order-field staffing-reason">回答期限（日本時間）<input type="datetime-local" value={deadline} onChange={e=>{setReview(false);setDeadline(e.target.value);}} /></label>
        {review ? <><p>打診先 {selected.length}名：{candidates.data?.items.filter(p=>selected.includes(p.id)).map(p=>p.name).join("、")}</p><blockquote>上記の案件に参加できるか教えてください。人数調整で見送りになる場合もあります。結果は改めて連絡しますので、少しお待ちください。</blockquote><p>ここでは募集内容を保存します。LINE送信は保存後の別操作です。</p><button type="button" className="btn create-button" disabled={save.isPending} onClick={()=>save.mutate("recruit")}>この内容で募集を作成</button></> : <button type="button" className="btn create-button" disabled={!selected.length || !deadline || save.isPending} onClick={()=>setReview(true)}>打診する内容を確認</button>}
      </> : null}
      {canWrite && item.source_active !== false && !item.recruitment_version_id ? <details><summary>本人と確認できたため、欠員を取り消す</summary><label className="order-field staffing-reason">復帰を確認した内容<textarea value={reason} onChange={e=>setReason(e.target.value)} /></label><button type="button" className="btn btn-line-blue" disabled={!reason.trim() || save.isPending} onClick={()=>save.mutate("cancel")}>欠員を取り消し、元の予定を戻す</button></details> : null}
    </> : <p>確認しています…</p>}
  </div></FormDialog>;
}
