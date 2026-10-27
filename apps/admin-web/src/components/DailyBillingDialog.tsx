import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../lib/api/client";
import type { BillingOrder } from "../lib/orderBillingApi";
import { BillingAmountInput } from "./BillingAmountInput";
import { groupedBillingAmount, isValidBillingAmount, normalizeBillingAmount } from "../lib/billingAmountFormat";
import { FormDialog } from "./FormDialog";
import { todayInTokyo } from "./MonthCalendar";
import "../styles/dailyBilling.css";

type Setting={project_id:string;base_rate:string;weekday_rates:Record<string,string>;revision:number};
type State={setting:Setting|null;dates:string[];is_test:boolean;client_id:string|null;previous_days?:{date:string;adjustment:string;adjustment_reason:string}[];projects:{id:string;name:string;code:string|null}[]};
type Day={date:string;weekday:number;quantity:number;unit_price:string;subtotal:string;workers:{name:string;worker_id:string;actual_ids:string[];minutes:number}[]};
type Preview={project_name:string;source_digest:string;rates_revision:number;excluded_count:number;needs_review:number;days:Day[]};
const weekdays=["月","火","水","木","金","土","日"];
const cents=(text:string):bigint|null=>{
  if(!/^[+-]?\d+(?:\.\d{0,2})?$/.test(text)) return null;
  const negative=text.startsWith("-");const [whole,fraction=""]=text.replace(/^[+-]/,"").split(".");
  return (BigInt(whole)*100n+BigInt((fraction+"00").slice(0,2)))*(negative?-1n:1n);
};
const money=(value:bigint)=>`${value<0n?"-":""}¥${new Intl.NumberFormat("ja-JP").format((value<0n?-value:value)/100n)}${value%100n?"."+String((value<0n?-value:value)%100n).padStart(2,"0"):""}`;
const signedDisplay=(value:string)=>value.startsWith("-")?"-"+groupedBillingAmount(value.slice(1)):groupedBillingAmount(value);

export function DailyBillingDialog({row,onClose}:{row:BillingOrder;onClose:()=>void}) {
  const cache=useQueryClient();
  const endpoint=`/api/order-billing/orders/${row.version_id}/daily`;
  const state=useQuery({queryKey:["order-billing","daily-setting",row.version_id],queryFn:()=>apiFetch<State>(endpoint)});
  const initialized=useRef(false);
  const [project,setProject]=useState("");const [base,setBase]=useState("");
  const [weekly,setWeekly]=useState<Record<string,string>>({});const [useWeekly,setUseWeekly]=useState(false);
  const [editing,setEditing]=useState(false);const [rateReason,setRateReason]=useState("");
  const [month,setMonth]=useState(row.billing_month?`${row.billing_month.slice(0,4)}-${row.billing_month.slice(4)}`:todayInTokyo().slice(0,7));
  const [adjustments,setAdjustments]=useState<Record<string,{amount:string;reason:string}>>({});
  const [reason,setReason]=useState("");const [incentive,setIncentive]=useState(row.incentive_amount??"");
  const [zeroConfirmed,setZeroConfirmed]=useState(false);const [reviewed,setReviewed]=useState(false);
  const [review,setReview]=useState(false);const [status,setStatus]=useState("");
  useEffect(()=>{
    if(!state.data || initialized.current) return;
    initialized.current=true;const setting=state.data.setting;
    setProject(setting?.project_id??"");setBase(setting?.base_rate??"");setWeekly(setting?.weekday_rates??{});
    setUseWeekly(Boolean(setting && Object.keys(setting.weekday_rates).length));setEditing(!setting);
    setAdjustments(Object.fromEntries((state.data.previous_days??[]).map(d=>[d.date,{amount:d.adjustment,reason:d.adjustment_reason}])));
  },[state.data]);
  const preview=useQuery({queryKey:["order-billing","daily-preview",row.version_id,state.data?.setting?.revision],enabled:!!state.data?.setting && !editing,queryFn:()=>apiFetch<Preview>(endpoint+"/preview")});
  useEffect(()=>{setReviewed(false);setReview(false);},[preview.data?.source_digest,preview.data?.rates_revision]);
  const saveRates=useMutation({mutationFn:()=>apiFetch<State>(endpoint+"/rates",{method:"PUT",body:JSON.stringify({project_id:project,base_rate:base,weekday_rates:useWeekly?Object.fromEntries(Object.entries(weekly).filter(([,v])=>v!=="")):{},revision:state.data?.setting?.revision??0,reason:rateReason})}),
    onSuccess:async result=>{cache.setQueryData(["order-billing","daily-setting",row.version_id],result);setEditing(false);setStatus("単価設定を保存しました。確定実績の人数を確認してください。");await cache.invalidateQueries({queryKey:["order-billing"]});}});
  const save=useMutation({mutationFn:()=>apiFetch(endpoint+"/confirm",{method:"POST",body:JSON.stringify({billing_month:month.replace("-",""),source_digest:preview.data?.source_digest,rates_revision:preview.data?.rates_revision,expected_revision:row.revision,
    adjustments:Object.fromEntries((preview.data?.days??[]).map(d=>[d.date,adjustments[d.date]??{amount:"0",reason:""}])),confirm_zero_days:zeroConfirmed,reason,incentive_amount:row.incentive_enabled && incentive!==""?incentive:null})}),
    onSuccess:async()=>{await cache.invalidateQueries({queryKey:["order-billing"]});onClose();}});
  const busy=save.isPending || saveRates.isPending;
  const days=preview.data?.days??[];
  const totals=days.map(day=>{const adjustment=cents(adjustments[day.date]?.amount??"0");return adjustment===null?null:BigInt(day.quantity)*(cents(day.unit_price)??0n)+adjustment;});
  const valid=totals.every(v=>v!==null && v>=0n) && days.every(d=>cents(adjustments[d.date]?.amount??"0")===0n || Boolean(adjustments[d.date]?.reason.trim()));
  const total=totals.reduce<bigint>((sum,v)=>sum+(v??0n),0n);
  const hasZero=days.some(d=>!d.quantity);
  const canConfirm=!!days.length && !!month && valid && reviewed && !preview.data?.needs_review && (!hasZero || (zeroConfirmed && !!reason.trim())) && (!row.revision || !!reason.trim()) && (!row.incentive_enabled || incentive==="" || isValidBillingAmount(incentive));
  const change=(day:string,key:"amount"|"reason",value:string)=>{setReview(false);setReviewed(false);setAdjustments({...adjustments,[day]:{amount:adjustments[day]?.amount??"0",reason:adjustments[day]?.reason??"",[key]:value}});};
  return <FormDialog open title="1人日単価で請求金額を確認" busy={busy} onClose={onClose}><div className="daily-billing-form">
    <p><strong>{row.is_test?"【テスト】":""}{row.project_name}</strong>　{row.document_number} 第{row.version_no}版<br />請求先：{row.client_name} ／ 稼働日：{row.work_date_label}</p>
    <p>確定実績の人数で計算します。同じ人・案件・日は1人日。稼働者の報酬単価とは別に設定します。</p>
    {state.error || preview.error || saveRates.error || save.error ? <p role="alert" className="form-error">{(state.error??preview.error??saveRates.error??save.error)?.message}</p>:null}
    {status?<p role="status">{status}</p>:null}
    {state.isLoading?<p>確認しています…</p>:null}
    {state.data && editing ? <fieldset disabled={busy}><legend>請求単価と実績の案件</legend>
      <div className="daily-billing-grid"><label className="order-field">人数を確認する実績の案件<select value={project} onChange={e=>setProject(e.target.value)}><option value="">実績の案件を選択</option>{state.data.projects.map(p=><option key={p.id} value={p.id}>{p.code?`${p.code} `:""}{p.name}</option>)}</select></label>
        <BillingAmountInput label="基本の1人日単価（税抜・円）" value={base} disabled={busy} onChange={setBase}/></div>
      {!state.data.projects.length?<p className="form-error">同じクライアントの実績案件がありません。案件を登録し、実績との対応を確認してください。</p>:null}
      <div className="daily-billing-actions" role="group" aria-label="請求単価の設定方法"><button type="button" className="btn btn-line-blue" aria-pressed={!useWeekly} onClick={()=>setUseWeekly(false)}>全曜日で基本単価</button><button type="button" className="btn btn-line-blue" aria-pressed={useWeekly} onClick={()=>setUseWeekly(true)}>曜日別に設定する</button></div>
      {useWeekly?<><p>変わる曜日だけ入力してください。空欄は基本単価を使います。祝日による自動変更は行いません。</p><div className="daily-billing-weekdays">{weekdays.map((day,i)=><BillingAmountInput key={day} label={`${day}曜日（税抜・円）`} value={weekly[String(i)]??""} disabled={busy} onChange={value=>setWeekly({...weekly,[String(i)]:value})}/>)}</div></>:null}
      {state.data.setting?<label className="order-field">単価設定を変える理由<textarea value={rateReason} maxLength={2000} onChange={e=>setRateReason(e.target.value)}/></label>:null}
      <button type="button" className="btn create-button" disabled={busy || !project || !isValidBillingAmount(base) || (useWeekly && Object.values(weekly).some(v=>v!==""&&!isValidBillingAmount(v))) || (!!state.data.setting&&!rateReason.trim())} onClick={()=>saveRates.mutate()}>単価設定を保存して実績を確認</button>
    </fieldset>:state.data?.setting?<div className="daily-billing-actions"><p>基本単価 {money(cents(state.data.setting.base_rate)??0n)} ／ 単価設定 第{state.data.setting.revision}版</p><button type="button" className="btn btn-line-blue" disabled={busy} onClick={()=>{setEditing(true);setReview(false);}}>単価設定を変更</button><button type="button" className="btn btn-line-blue" disabled={busy||preview.isFetching} onClick={()=>{setReviewed(false);setReview(false);void preview.refetch();}}>実績を読み直す</button></div>:null}
    {!editing && preview.data?<>
      <p>実績の案件：{preview.data.project_name} ／ 有効な確定実績を集計。取消済みの配置など {preview.data.excluded_count}件は除外しています。</p>
      {preview.data.needs_review?<p className="form-error">要確認の実績があります。実績の確認を終えてから確定してください。</p>:null}
      <div className="daily-billing-table"><table className="data-table"><thead><tr><th>稼働日</th><th>確定実績の人数</th><th>1人日単価</th><th>個別調整（±円）と理由</th><th>日別小計</th></tr></thead><tbody>{days.map((day,i)=><tr key={day.date}><td>{day.date}（{weekdays[day.weekday]}）</td><td>{day.quantity}人<ul>{day.workers.map(w=><li key={w.worker_id}>{w.name}{w.minutes===0?"（実績0分・確認）":""}</li>)}</ul></td><td>{money(cents(day.unit_price)??0n)}</td><td><input aria-label={`${day.date}の調整額`} type="text" inputMode="decimal" value={signedDisplay(adjustments[day.date]?.amount??"0")} onChange={e=>change(day.date,"amount",normalizeBillingAmount(e.target.value))}/><input aria-label={`${day.date}の調整理由`} placeholder="調整した場合は理由を入力" value={adjustments[day.date]?.reason??""} maxLength={2000} onChange={e=>change(day.date,"reason",e.target.value)}/></td><td>{totals[i]===null?"入力を確認":money(totals[i]!)}</td></tr>)}</tbody></table></div>
      <p className="daily-billing-total">通常請求額（税抜） {money(total)}</p>
      {row.amount!==null?<p>これまでの通常請求額 {money(cents(row.amount)??0n)} ／ 差額 {money(total-(cents(row.amount)??0n))}。新しく確定するまで旧額を保持します。</p>:null}
      <p>半日などは人数を自動で減らしません。必要な金額差を調整欄へ入力し、根拠を記録してください。条件メモから金額を自動計算しません。</p>
      <label className="order-field">請求月<input type="month" value={month} onChange={e=>{setMonth(e.target.value);setReview(false);}}/></label>
      {row.incentive_enabled?<fieldset><legend>インセンティブ条件</legend><p className="order-cell-multiline">{row.incentive_note}</p><BillingAmountInput label="インセンティブ額（税抜・円、未確定は空欄）" value={incentive} disabled={busy} onChange={v=>{setIncentive(v);setReview(false);}}/></fieldset>:null}
      <label className="order-field">{row.revision || hasZero?"確認内容・変更理由（必須）":"確認内容・記録メモ"}<textarea value={reason} maxLength={2000} onChange={e=>setReason(e.target.value)}/></label>
      {hasZero?<label className="daily-billing-check"><input type="checkbox" checked={zeroConfirmed} onChange={e=>{setZeroConfirmed(e.target.checked);setReview(false);}}/>実績0人の日を確認し、無稼働として確定する（記録メモが必要）</label>:null}
      <label className="daily-billing-check"><input type="checkbox" checked={reviewed} onChange={e=>{setReviewed(e.target.checked);setReview(false);}}/>日別人数・単価・調整額を運営で確認しました</label>
      {review?<div className="daily-billing-review"><p>{month}分の通常請求額 {money(total)} を保存します。日別明細と実績の根拠を固定して残します。</p>{row.incentive_enabled?<p>{incentive===""?"インセンティブは未確定です。通常請求額のみ保存し、請求書作成は保留します。":`インセンティブ ${money(cents(incentive)??0n)} ／ 合計（税抜） ${money(total+(cents(incentive)??0n))}`}</p>:null}<button type="button" className="btn create-button" disabled={busy||!canConfirm} onClick={()=>save.mutate()}>{busy?"保存しています…":"この明細で請求金額を確定"}</button><button type="button" className="btn btn-ghost" disabled={busy} onClick={()=>setReview(false)}>戻る</button></div>:<button type="button" className="btn create-button" disabled={busy||!canConfirm} onClick={()=>setReview(true)}>日別明細と金額を最終確認</button>}
    </>:null}
  </div></FormDialog>;
}
