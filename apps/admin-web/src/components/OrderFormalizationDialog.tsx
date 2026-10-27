import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiFetch } from '../lib/api/client';
import { sectionsFromStored } from '../lib/orderRequestFormat';
import { scheduleFees, scheduleHours } from '../lib/orderSchedule';
import type { InternalOrderSource, OrderRequestVersion } from '../types/orderRequest';
import { FormDialog } from './FormDialog';
import { OrderInternalSourceEditor } from './OrderInternalSourceEditor';
import '../styles/orderFormalization.css';

type Relation={source_document_number:string;source_version_id:string;formal_document_number:string;formal_version_id:string;formal_status:string;formal_hidden:boolean};
type Preview={existing:Relation|null;source_digest:string;document_number:string;work_date_label:string;request_conditions:string;body:string;site_name:string;contact_name:string;capacities:Record<string,number>;source_candidates:{id:string;name:string;active:boolean}[];rate_reference?:{base_rate:string;weekday_rates:Record<string,string>}|null};

export function OrderFormalizationDialog({versionId,workers,onClose,onCreated}:{versionId:string;workers:{id:string;name:string}[];onClose:()=>void;onCreated:(versionId:string)=>void}) {
  const endpoint=`/api/order-requests/versions/${versionId}/formalization`;
  const preview=useQuery({queryKey:['order-formalization',versionId],queryFn:()=>apiFetch<Preview>(endpoint),staleTime:0});
  const [source,setSource]=useState<InternalOrderSource|null>(null);
  const [ids,setIds]=useState<string[]>([]);const [search,setSearch]=useState('');
  const [capacities,setCapacities]=useState<Record<string,number>>({});
  const [reviewed,setReviewed]=useState(false);
  const [deadline,setDeadline]=useState('');
  useEffect(()=>{setCapacities(preview.data?.capacities??{});setReviewed(false);},[preview.data?.source_digest]);
  const create=useMutation({mutationFn:()=>apiFetch<OrderRequestVersion>(endpoint,{method:'POST',body:JSON.stringify({source_digest:preview.data?.source_digest,internal_source:source?{client_id:source.client_id,client_staff_id:source.client_staff_id}:null,worker_ids:ids,capacities,masters_reviewed:reviewed,follow_up_due_on:deadline})}),onSuccess:version=>onCreated(version.id)});
  const value=preview.data;
  const existing=value?.existing;
  const sections=value&&!existing?sectionsFromStored(value.request_conditions,value.body):null;
  const schedule=sections?.schedule?{...sections.schedule,work_groups:sections.schedule.work_groups.map(g=>({...g,notes:g.notes??''})),rate_groups:sections.schedule.rate_groups.map(g=>({...g,notes:g.notes??''}))}:null;
  const canCreate=!!value&&!existing&&!!source?.client_id&&!!deadline&&ids.length>0&&ids.length<=40&&reviewed&&Object.values(capacities).every(v=>Number.isInteger(v)&&v>=0&&v<=10000);
  return <FormDialog open title="テスト案件から正式版を作成" busy={create.isPending} onClose={onClose}><div className="order-formalization">
    {preview.isLoading?<p>元のテスト内容を確認しています…</p>:null}
    {preview.error||create.error?<p role="alert" className="form-error">{(preview.error??create.error)?.message}</p>:null}
    {existing?<><p>正式版 {existing.formal_document_number} は作成済みです。繰り返し作成はしません。</p>{existing.formal_hidden?<p>正式版は一覧から外されています。削除済み案件一覧で確認してください。</p>:<button type="button" className="btn btn-line-blue" onClick={()=>onCreated(existing.formal_version_id)}>作成済みの正式版を開く</button>}</>:value&&sections?<>
      <p>元のテストを残して、別番号の正式な下書きを作ります。この操作ではLINEを送りません。</p>
      <fieldset><legend>引き継ぐ案件内容</legend>
        <p><strong>{sections.projectName}</strong> ／ {value.document_number}<br/>{value.work_date_label} ／ {value.site_name}<br/>連絡担当：{value.contact_name}</p>
        <p className="order-formalization-text">{schedule?scheduleHours(schedule):sections.hours}</p>
        <p className="order-formalization-text">稼働者への報酬：{schedule?scheduleFees(schedule):sections.fee}</p>
        <details><summary>業務内容・注意書きを確認</summary><p className="order-formalization-text">{[sections.content,sections.notes].filter(Boolean).join('\n')}</p><p className="order-formalization-text">{sections.incentive}</p></details>
        {value.rate_reference?<p>請求の参考単価：基本 {Number(value.rate_reference.base_rate).toLocaleString('ja-JP')}円／人日{Object.entries(value.rate_reference.weekday_rates).map(([day,price])=>` ／ ${'月火水木金土日'[Number(day)]}曜 ${Number(price).toLocaleString('ja-JP')}円`).join('')}。正式な実績案件・金額は請求画面で確認します。</p>:null}
      </fieldset>
      <p>テストの参加回答・欠員手配・起床報告・送信履歴・確定金額は引き継ぎません。日程や条件は作成後の下書きで編集できます。</p>
      <label className="order-field">正式版の回答期限（21:00）<input type="date" value={deadline} onChange={e=>{setDeadline(e.target.value);setReviewed(false);}}/></label>
      <OrderInternalSourceEditor value={source} disabled={create.isPending} onChange={v=>{setSource(v);setReviewed(false);}}/>
      <fieldset><legend>正式な送付候補を選択（最大40人）</legend>
        <p>テスト時の候補（参考）：{value.source_candidates.map(w=>w.name+(w.active?'':'（無効）')).join('、')||'なし'}</p>
        <label className="order-field">候補者を検索<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="氏名で検索"/></label>
        <p>選択：{ids.length}人 ／ {workers.filter(w=>ids.includes(w.id)).map(w=>w.name).join('、')||'未選択'}</p>
        <div className="order-formalization-workers">{workers.filter(w=>w.name.includes(search.trim())).map(w=><label className="order-check" key={w.id}><input type="checkbox" checked={ids.includes(w.id)} disabled={create.isPending||(!ids.includes(w.id)&&ids.length>=40)} onChange={e=>{setIds(e.target.checked?[...ids,w.id]:ids.filter(id=>id!==w.id));setReviewed(false);}}/>{w.name}</label>)}</div>
      </fieldset>
      <fieldset><legend>案件・日付ごとの募集上限</legend><p>テスト時の上限を表示しています。参加者は正式版への回答後、運営が改めて決定します。</p><div className="order-formalization-capacities">{Object.keys(capacities).sort().map(day=><label className="order-field" key={day}>{day}<input type="number" min={0} max={10000} value={Number.isNaN(capacities[day])?'':capacities[day]} onChange={e=>{setCapacities({...capacities,[day]:e.target.value===''?NaN:Number(e.target.value)});setReviewed(false);}}/></label>)}</div></fieldset>
      <label className="order-check"><input type="checkbox" checked={reviewed} disabled={create.isPending} onChange={e=>setReviewed(e.target.checked)}/>案件内容・正式な発注元・候補者・募集上限を確認しました</label>
      <button type="button" className="btn create-button" disabled={!canCreate||create.isPending} onClick={()=>create.mutate()}>{create.isPending?'作成しています…':'確認して正式な下書きを作成'}</button>
    </>:null}
  </div></FormDialog>;
}
