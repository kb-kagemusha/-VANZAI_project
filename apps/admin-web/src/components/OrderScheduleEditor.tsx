import { confirmApp } from "../lib/appDialog";
import { dateGroupLabel, newRateGroup, newWorkGroup, syncSchedule, type DateGroup, type OrderSchedule } from "../lib/orderSchedule";

function DateInputs({ group, disabled, prefix, onChange }: { group: DateGroup; disabled: boolean; prefix: string; onChange: (group: DateGroup) => void }) {
  return <div className="order-schedule-dates">
    <div className="order-date-mode">
      <span>日付の設定</span>
      <div className="order-option-buttons" role="group" aria-label={`${prefix}日付の設定`}>
        {([ ["single", "1日ごと"], ["range", "複数日の期間"] ] as const).map(([mode, label]) =>
          <button key={mode} type="button" disabled={disabled} aria-pressed={group.date_mode === mode}
            onClick={() => onChange({ ...group, date_mode: mode })}>{label}</button>)}
      </div>
    </div>
    <label>{group.date_mode === "range" ? "開始日" : "稼働日"}
      <input type="date" aria-label={`${prefix}開始日`} value={group.from} disabled={disabled}
        onChange={(e) => onChange({ ...group, from: e.target.value, to: group.date_mode === "single" ? e.target.value : group.to })} />
    </label>
    {group.date_mode === "range" && <label>終了日
      <input type="date" aria-label={`${prefix}終了日`} value={group.to} min={group.from || undefined} disabled={disabled}
        onChange={(e) => onChange({ ...group, to: e.target.value })} />
    </label>}
  </div>;
}

export function OrderScheduleEditor({ schedule, disabled, onChange }: { schedule: OrderSchedule; disabled: boolean; onChange: (schedule: OrderSchedule) => void }) {
  const value = syncSchedule(schedule);
  const change = (next: OrderSchedule) => onChange(syncSchedule(next));

  async function removeWork(id: string) {
    const accepted = await confirmApp({ title: "稼働日の削除", message: "この日付・期間の詳細を削除します。単価を稼働日に合わせている場合、対応する単価設定も削除します。", confirmLabel: "削除", tone: "danger" });
    if (accepted) change({ ...value, work_groups: value.work_groups.filter((g) => g.id !== id) });
  }

  async function followWork(checked: boolean) {
    if (checked && value.rate_groups.length && !value.rates_follow_work) {
      const accepted = await confirmApp({ title: "単価の日付設定", message: "稼働日と同じ分け方にします。日付・期間が一致する単価は引き継ぎ、それ以外の単価は入力し直します。", confirmLabel: "稼働日に合わせる" });
      if (!accepted) return;
    }
    change({ ...value, rates_follow_work: checked, rate_groups: checked ? value.rate_groups : value.rate_groups.map((g) => ({ ...g, work_group_id: null })) });
  }

  async function useDailyRate(id: string) {
    const accepted = await confirmApp({ title: "日給へ変更", message: "保存済みの旧時給を日給に変更します。金額は自動換算しません。変更後に日給額を入力してください。", confirmLabel: "日給を入力する" });
    if (accepted) change({ ...value, rate_groups: value.rate_groups.map((g) => g.id === id ? { ...g, unit: "day", amount: "" } : g) });
  }

  return <div className="order-schedule order-span-12">
    <h5>稼働日・稼働時間</h5>
    <p className="order-field-hint">同じ時間・条件の日は期間でまとめられます。日付が重複しないように設定してください。</p>
    {value.work_groups.map((group, index) => {
      const update = (patch: Partial<typeof group>) => change({ ...value, work_groups: value.work_groups.map((g) => g.id === group.id ? { ...g, ...patch } : g) });
      const showOvernight = group.end_next_day || Boolean(group.start_time && group.end_time && group.end_time <= group.start_time);
      return <fieldset key={group.id} className="order-schedule-row order-work-row" disabled={disabled}>
        <legend>稼働日の詳細 {index + 1}</legend>
        <DateInputs group={group} prefix={`稼働日の詳細${index + 1}の`} disabled={disabled} onChange={update} />
        <div className="order-schedule-times">
          <label>開始時間<input type="time" value={group.start_time} onChange={(e) => update({ start_time: e.target.value })} /></label>
          <label>終了時間<input type="time" value={group.end_time} onChange={(e) => update({ end_time: e.target.value })} /></label>
        </div>
        {showOvernight && <div className="order-overnight-notice">
          <label className="order-check"><input type="checkbox" checked={group.end_next_day} onChange={(e) => update({ end_next_day: e.target.checked })} />日をまたいで翌日に終了する</label>
          <p>22:00開始・翌朝6:00終了などの日をまたぐ稼働に使います。終了時間の入力違いでないことを確認してください。</p>
        </div>}
        <label>稼働日の備考<textarea rows={2} value={group.notes} onChange={(e) => update({ notes: e.target.value })} /></label>
        {group.gathering_time && <details className="order-field-hint"><summary>保存済みの旧項目（参考）</summary><p>旧集合時間：{group.gathering_time}</p></details>}
        {!disabled && <div className="order-schedule-actions"><button type="button" className="order-action-button is-remove" onClick={() => void removeWork(group.id)}>稼働日の詳細 {index + 1} を削除</button></div>}
      </fieldset>;
    })}
    {!disabled && <div className="order-schedule-actions"><button type="button" className="order-action-button is-add" onClick={() => change({ ...value, work_groups: [...value.work_groups, newWorkGroup()] })}><span aria-hidden="true">＋</span> 稼働日・期間を追加</button></div>}

    <h5>単価</h5>
    <label className="order-check order-rate-sync"><input type="checkbox" checked={value.rates_follow_work} disabled={disabled} onChange={(e) => void followWork(e.target.checked)} />稼働日の設定で単価設定する</label>
    {value.rate_groups.map((group, index) => {
      const update = (patch: Partial<typeof group>) => change({ ...value, rate_groups: value.rate_groups.map((g) => g.id === group.id ? { ...g, ...patch } : g) });
      return <fieldset key={group.id} className="order-schedule-row order-rate-row" disabled={disabled}>
        <legend>単価 {index + 1}：{dateGroupLabel(group) || "日付未設定"}</legend>
        {!value.rates_follow_work && <DateInputs group={group} prefix={`単価${index + 1}の`} disabled={disabled} onChange={update} />}
        <div className="order-schedule-times">
          <label>単価（円・税抜）<input type="number" min="0" step="0.01" readOnly={group.unit === "hour"} value={group.amount} onChange={(e) => update({ amount: e.target.value })} /></label>
          <div className="order-date-mode"><span>単位：{group.unit === "hour" ? "保存済みの旧時給" : "日給"}</span>
            {group.unit === "hour" && <><p className="order-field-hint">旧条件を保持しています。日給額を入力する場合は変更してください。</p>{!disabled && <button type="button" className="btn btn-ghost" onClick={() => void useDailyRate(group.id)}>日給へ変更</button>}</>}
          </div>
        </div>
        <div className="order-expense-grid">
          <div className="order-expense-cell">
            <label className="order-check"><input type="checkbox" checked={group.lunch_included} onChange={(e) => update({ lunch_included: e.target.checked })} />昼食代：込み</label>
            {!group.lunch_included && <label>昼食代の備考<textarea rows={2} value={group.lunch_note} onChange={(e) => update({ lunch_note: e.target.value })} /></label>}
          </div>
          <div className="order-expense-cell">
            <label className="order-check"><input type="checkbox" checked={group.transport_included} onChange={(e) => update({ transport_included: e.target.checked })} />交通費：込み</label>
            {!group.transport_included && <label>交通費の備考<textarea rows={2} value={group.transport_note} onChange={(e) => update({ transport_note: e.target.value })} /></label>}
          </div>
        </div>
        <label>単価の備考<textarea rows={2} value={group.notes} onChange={(e) => update({ notes: e.target.value })} /></label>
        {!disabled && !value.rates_follow_work && <div className="order-schedule-actions"><button type="button" className="order-action-button is-remove" onClick={() => change({ ...value, rate_groups: value.rate_groups.filter((g) => g.id !== group.id) })}>単価 {index + 1} を削除</button></div>}
      </fieldset>;
    })}
    {!disabled && !value.rates_follow_work && <div className="order-schedule-actions"><button type="button" className="order-action-button is-add" onClick={() => change({ ...value, rate_groups: [...value.rate_groups, newRateGroup()] })}><span aria-hidden="true">＋</span> 単価の日付・期間を追加</button></div>}
  </div>;
}
