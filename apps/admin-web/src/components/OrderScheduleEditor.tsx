import { confirmApp } from "../lib/appDialog";
import { useState } from "react";
import { MonthCalendar, monthOf } from "./MonthCalendar";
import { OrderDatePicker } from "./OrderDatePicker";
import "../styles/monthCalendar.css";
import { dateGroupLabel, newRateGroup, newWorkGroup, syncSchedule, type DateGroup, type OrderSchedule } from "../lib/orderSchedule";

/**
 * 全体の稼働日の中の休業日（DEC-065、0.48.5 で全体の稼働日の横へ移動）。
 * 「休業日を設定」を押すと期間のカレンダーが出て、日付を押して選び（もう一度押すと外れる）、「OK」で確定する。
 * 期間を変えて範囲外になった日は自動で消さず、表示して見直してもらう。
 */
export function HolidayPicker({ from, to, dates, disabled, onChange }: { from: string; to: string; dates: string[]; disabled: boolean; onChange: (dates: string[]) => void }) {
  const group = { from, to };
  const prefix = "";
  const [editing, setEditing] = useState<string[] | null>(null);
  const [month, setMonth] = useState("");
  const [notice, setNotice] = useState("");
  const ready = Boolean(group.from && group.to && group.from < group.to);
  const inRange = (day: string) => Boolean(group.from && group.to && day >= group.from && day <= group.to);
  const label = (day: string) => dateGroupLabel({ id: day, date_mode: "single", from: day, to: day });

  function open() {
    setEditing([...dates]);
    setMonth(monthOf(group.from));
    setNotice("");
  }
  function toggle(day: string) {
    setEditing((current) => (current ? (current.includes(day) ? current.filter((d) => d !== day) : [...current, day].sort()) : current));
  }
  function confirm() {
    if (!editing) return;
    // 期間外になっていた日は、カレンダーでは選べないのでここで外す
    const next = editing.filter(inRange).sort();
    onChange(next);
    setEditing(null);
    setNotice(next.length ? `休業日を設定しました（${next.length}日）` : "休業日はなしにしました");
  }

  return <div className="order-excluded-dates" role="group" aria-label={`${prefix}休業日`}>
    <span className="order-field-label">休業日（稼働日の中で稼働しない日）</span>
    {dates.length > 0
      ? <div className="order-recipient-picks">{dates.map((day) => <span key={day} className={`order-pick${inRange(day) ? "" : " is-error"}`}>
          {label(day)}{inRange(day) ? "" : "（期間外）"}
        </span>)}</div>
      : <p className="order-field-hint">休業日はありません。</p>}
    {!disabled && dates.some((day) => !inRange(day)) ? (
      <div className="order-schedule-actions">
        <span className="form-error">稼働日を変えたため、期間外の休業日があります。</span>
        <button type="button" className="order-action-button is-remove" onClick={() => { const next = dates.filter(inRange); onChange(next); setNotice(`期間外の休業日を外しました（残り${next.length}日）`); }}>期間外の日を外す</button>
      </div>
    ) : null}
    {notice ? <p className="order-excluded-notice" role="status">{notice}</p> : null}
    {!disabled && editing === null && (
      <div className="order-schedule-actions">
        <button type="button" className="order-action-button order-excluded-open" disabled={!ready} onClick={open}>
          <span aria-hidden="true">＋</span> {dates.length ? "休業日を変更" : "休業日を設定"}
        </button>
        {!ready ? <span className="order-field-hint">稼働日の開始日と終了日（2日以上）を入れると設定できます</span> : null}
      </div>
    )}
    {!disabled && editing !== null && (
      <div className="order-excluded-panel">
        <p className="order-field-hint">押した日が休業日になります（もう一度押すと戻ります）。「OK」で確定します。</p>
        <MonthCalendar
          month={month}
          onMonthChange={setMonth}
          minMonth={monthOf(group.from)}
          maxMonth={monthOf(group.to)}
          className="order-excluded-calendar"
          renderDay={(day) => {
            const usable = inRange(day);
            const off = editing.includes(day);
            return <button type="button" className={`order-excluded-day${usable ? "" : " is-out"}${off ? " is-off" : ""}`}
              disabled={!usable} aria-pressed={off} onClick={() => toggle(day)}>
              <span>{Number(day.slice(8))}</span>
              {usable ? <small>{off ? "休業" : "稼働"}</small> : null}
            </button>;
          }}
        />
        <p className="order-excluded-summary">{editing.filter(inRange).length ? `休業日：${editing.filter(inRange).map(label).join("、")}` : "休業日：なし"}</p>
        <div className="order-schedule-actions">
          <button type="button" className="btn btn-primary btn-sm" onClick={confirm}>OK</button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(null)}>キャンセル</button>
        </div>
      </div>
    )}
  </div>;
}

function DateInputs({ group, disabled, prefix, periodFrom, periodTo, onChange }: { group: DateGroup; disabled: boolean; prefix: string; periodFrom: string; periodTo: string; onChange: (group: DateGroup) => void }) {
  const ready = Boolean(periodFrom && periodTo && periodFrom <= periodTo);
  const endMin = group.from && group.from > periodFrom ? group.from : periodFrom;
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
      <OrderDatePicker label={`${prefix}開始日`} value={group.from} min={periodFrom || undefined} max={periodTo || undefined} disabled={disabled || !ready}
        onChange={(day) => onChange({ ...group, from: day, to: group.date_mode === "single" ? day : group.to })} />
    </label>
    {group.date_mode === "range" && <label>終了日
      <OrderDatePicker label={`${prefix}終了日`} value={group.to} min={endMin || undefined} max={periodTo || undefined} disabled={disabled || !ready || endMin > periodTo}
        onChange={(day) => onChange({ ...group, to: day })} />
    </label>}
    {!ready ? <p className="order-field-hint">上の「稼働日」で開始日と終了日を設定してください。</p> : null}
    {ready && [group.from, group.to].some((day) => day && (day < periodFrom || day > periodTo)) ? <p className="form-error">全体の稼働期間外の日付があります。日付を選び直してください。</p> : null}
  </div>;
}

export function OrderScheduleEditor({ schedule, disabled, periodFrom, periodTo, templateMode = false, onChange }: { schedule: OrderSchedule; disabled: boolean; periodFrom: string; periodTo: string; templateMode?: boolean; onChange: (schedule: OrderSchedule) => void }) {
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
    <h5>稼働時間の詳細</h5>
    <p className="order-field-hint">上で設定した全体の稼働期間内で、日ごと・期間ごとの開始時間と終了時間を入力してください。同じ時間・条件の日は期間でまとめられます。</p>
    {value.work_groups.map((group, index) => {
      const update = (patch: Partial<typeof group>) => change({ ...value, work_groups: value.work_groups.map((g) => {
        if (g.id !== group.id) return g;
        const next = { ...g, ...patch };
        // 1日ごとの稼働日には休業日を持たせない（サーバーも拒否する）。
        return next.date_mode === "single" ? { ...next, excluded_dates: [] } : next;
      }) });
      const showOvernight = group.end_next_day || Boolean(group.start_time && group.end_time && group.end_time <= group.start_time);
      return <fieldset key={group.id} className="order-schedule-row order-work-row" disabled={disabled}>
        <legend>稼働日の詳細 {index + 1}</legend>
        {!templateMode && <DateInputs group={group} prefix={`稼働日の詳細${index + 1}の`} periodFrom={periodFrom} periodTo={periodTo} disabled={disabled} onChange={update} />}
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
        <legend>単価 {index + 1}{!templateMode ? `：${dateGroupLabel(group) || "日付未設定"}` : ""}</legend>
        {!templateMode && !value.rates_follow_work && <DateInputs group={group} prefix={`単価${index + 1}の`} periodFrom={periodFrom} periodTo={periodTo} disabled={disabled} onChange={update} />}
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
