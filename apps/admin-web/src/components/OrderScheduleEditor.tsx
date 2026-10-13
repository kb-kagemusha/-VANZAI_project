import { confirmApp } from "../lib/appDialog";
import { dateGroupLabel, newRateGroup, newWorkGroup, syncSchedule, type DateGroup, type OrderSchedule } from "../lib/orderSchedule";

function DateInputs({ group, disabled, prefix, onChange }: { group: DateGroup; disabled: boolean; prefix: string; onChange: (group: DateGroup) => void }) {
  return <div className="order-schedule-dates">
    <label>日付の設定<select aria-label={`${prefix}日付の設定`} value={group.date_mode} disabled={disabled}
      onChange={(e) => onChange({ ...group, date_mode: e.target.value as DateGroup["date_mode"], to: e.target.value === "single" ? group.from : group.to })}>
      <option value="single">1日ごと</option><option value="range">複数日の期間</option>
    </select></label>
    <label>{group.date_mode === "range" ? "開始日" : "稼働日"}<input type="date" aria-label={`${prefix}開始日`} value={group.from} disabled={disabled}
      onChange={(e) => onChange({ ...group, from: e.target.value, to: group.date_mode === "single" ? e.target.value : group.to })} /></label>
    {group.date_mode === "range" && <label>終了日<input type="date" aria-label={`${prefix}終了日`} value={group.to} min={group.from || undefined} disabled={disabled}
      onChange={(e) => onChange({ ...group, to: e.target.value })} /></label>}
  </div>;
}

export function OrderScheduleEditor({ schedule, disabled, onChange }: { schedule: OrderSchedule; disabled: boolean; onChange: (schedule: OrderSchedule) => void }) {
  const value = syncSchedule(schedule);
  const change = (next: OrderSchedule) => onChange(syncSchedule(next));
  async function removeWork(id: string) {
    const accepted = await confirmApp({ title: "稼働日の削除", message: "この日付・期間の勤務条件を削除します。単価を稼働日に合わせている場合、対応する単価設定も削除します。", confirmLabel: "削除", tone: "danger" });
    if (accepted) change({ ...value, work_groups: value.work_groups.filter((g) => g.id !== id) });
  }
  async function followWork(checked: boolean) {
    if (checked && value.rate_groups.length && !value.rates_follow_work) {
      const accepted = await confirmApp({ title: "単価の日付設定", message: "稼働日と同じ分け方にします。日付・期間が一致する単価は引き継ぎ、それ以外の単価は入力し直します。", confirmLabel: "稼働日に合わせる" });
      if (!accepted) return;
    }
    change({ ...value, rates_follow_work: checked, rate_groups: checked ? value.rate_groups : value.rate_groups.map((g) => ({ ...g, work_group_id: null })) });
  }
  return <div className="order-schedule order-span-12">
    <h5>稼働日・稼働時間</h5>
    <p className="order-field-hint">同じ時間・条件の日は期間でまとめられます。日付が重複しないように設定してください。</p>
    {value.work_groups.map((group, index) => <fieldset key={group.id} className="order-schedule-row" disabled={disabled}>
      <legend>勤務条件 {index + 1}</legend>
      <DateInputs group={group} prefix={`勤務条件${index + 1}の`} disabled={disabled} onChange={(dates) => change({ ...value, work_groups: value.work_groups.map((g) => g.id === group.id ? { ...g, ...dates } : g) })} />
      <div className="order-schedule-times">
        <label>開始時間<input type="time" value={group.start_time} onChange={(e) => change({ ...value, work_groups: value.work_groups.map((g) => g.id === group.id ? { ...g, start_time: e.target.value } : g) })} /></label>
        <label>終了時間<input type="time" value={group.end_time} onChange={(e) => change({ ...value, work_groups: value.work_groups.map((g) => g.id === group.id ? { ...g, end_time: e.target.value } : g) })} /></label>
        <label className="order-check"><input type="checkbox" checked={group.end_next_day} onChange={(e) => change({ ...value, work_groups: value.work_groups.map((g) => g.id === group.id ? { ...g, end_next_day: e.target.checked } : g) })} />終了は翌日</label>
        <label>集合時間（任意）<input type="time" value={group.gathering_time} onChange={(e) => change({ ...value, work_groups: value.work_groups.map((g) => g.id === group.id ? { ...g, gathering_time: e.target.value } : g) })} /></label>
      </div>
      <label>勤務の備考<textarea rows={2} value={group.notes} onChange={(e) => change({ ...value, work_groups: value.work_groups.map((g) => g.id === group.id ? { ...g, notes: e.target.value } : g) })} /></label>
      {!disabled && <button type="button" className="btn btn-ghost" onClick={() => void removeWork(group.id)}>勤務条件 {index + 1} を削除</button>}
    </fieldset>)}
    {!disabled && <button type="button" className="btn btn-ghost" onClick={() => change({ ...value, work_groups: [...value.work_groups, newWorkGroup()] })}>稼働日・期間を追加</button>}
    <h5>単価</h5>
    <label className="order-check"><input type="checkbox" checked={value.rates_follow_work} disabled={disabled} onChange={(e) => void followWork(e.target.checked)} />稼働日の設定で単価設定する</label>
    {value.rate_groups.map((group, index) => {
      const update = (patch: Partial<typeof group>) => change({ ...value, rate_groups: value.rate_groups.map((g) => g.id === group.id ? { ...g, ...patch } : g) });
      return <fieldset key={group.id} className="order-schedule-row" disabled={disabled}>
        <legend>単価 {index + 1}：{dateGroupLabel(group) || "日付未設定"}</legend>
        {!value.rates_follow_work && <DateInputs group={group} prefix={`単価${index + 1}の`} disabled={disabled} onChange={update} />}
        <div className="order-schedule-times">
          <label>単価（円・税抜）<input type="number" min="0" step="0.01" value={group.amount} onChange={(e) => update({ amount: e.target.value })} /></label>
          <label>単位<select value={group.unit} onChange={(e) => update({ unit: e.target.value as "day" | "hour" })}><option value="day">日給</option><option value="hour">時給</option></select></label>
          <label className="order-check"><input type="checkbox" checked={group.lunch_included} onChange={(e) => update({ lunch_included: e.target.checked })} />昼食代：込み</label>
          <label className="order-check"><input type="checkbox" checked={group.transport_included} onChange={(e) => update({ transport_included: e.target.checked })} />交通費：込み</label>
        </div>
        {!group.lunch_included && <label>昼食代の備考<textarea rows={2} value={group.lunch_note} onChange={(e) => update({ lunch_note: e.target.value })} /></label>}
        {!group.transport_included && <label>交通費の備考<textarea rows={2} value={group.transport_note} onChange={(e) => update({ transport_note: e.target.value })} /></label>}
        <label>単価の備考<textarea rows={2} value={group.notes} onChange={(e) => update({ notes: e.target.value })} /></label>
        {!disabled && !value.rates_follow_work && <button type="button" className="btn btn-ghost" onClick={() => change({ ...value, rate_groups: value.rate_groups.filter((g) => g.id !== group.id) })}>単価 {index + 1} を削除</button>}
      </fieldset>;
    })}
    {!disabled && !value.rates_follow_work && <button type="button" className="btn btn-ghost" onClick={() => change({ ...value, rate_groups: [...value.rate_groups, newRateGroup()] })}>単価の日付・期間を追加</button>}
  </div>;
}
