import { useState } from "react";
import { apiFetch } from "../lib/api/client";
import { syncSchedule, type OrderSchedule } from "../lib/orderSchedule";

type Holiday = { day: string; name: string; is_holiday: boolean; revision: number; source: string };

/** Public holidays differ from non-working days; edits update the shared calendar. */
export function OrderPublicHolidayPicker({ from, to, schedule, disabled, onChange }: {
  from: string; to: string; schedule: OrderSchedule; disabled: boolean; onChange: (value: OrderSchedule) => void;
}) {
  const [rows, setRows] = useState<Holiday[] | null>(null);
  const [loadedPeriod, setLoadedPeriod] = useState("");
  const [day, setDay] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const key = `${from}/${to}`;
  const valid = Boolean(from && to && from <= to);

  async function load() {
    setBusy(true); setMessage("");
    try {
      const result = await apiFetch<Holiday[]>(`/api/order-requests/holiday-calendar?start=${encodeURIComponent(from)}&end=${encodeURIComponent(to)}`);
      setRows(result); setLoadedPeriod(key);
    } catch (error) { setMessage(error instanceof Error ? error.message : "祝日一覧を取得できませんでした"); }
    finally { setBusy(false); }
  }
  async function update(target: string, isHoliday: boolean, label: string, revision: number) {
    setBusy(true); setMessage("");
    try {
      await apiFetch("/api/order-requests/holiday-calendar", { method: "PUT", body: JSON.stringify({ day: target, is_holiday: isHoliday, name: label, revision }) });
      await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "祝日一覧を更新できませんでした"); }
    finally { setBusy(false); }
  }
  async function apply() {
    if (!rows || loadedPeriod !== key) return;
    setBusy(true); setMessage("");
    try {
      const confirmed = await apiFetch<Holiday[]>("/api/order-requests/holiday-calendar/confirm", { method: "POST", body: JSON.stringify({ start: from, end: to, days: rows.filter((row) => row.is_holiday).map((row) => row.day) }) });
      const holidays = confirmed.filter((row) => row.is_holiday).map((row) => row.day);
      setRows(confirmed);
      onChange(syncSchedule({ ...schedule, work_groups: schedule.work_groups.map((group) => group.date_mode !== "weekly" ? group : {
        ...group, holiday_dates: holidays.filter((value) => value >= group.from && value <= group.to), holiday_review_from: group.from, holiday_review_to: group.to,
      }) }));
      setMessage("祝日一覧を依頼書に反映しました。日付と条件を確認してください。");
    } catch (error) { setMessage(error instanceof Error ? error.message : "祝日一覧を確定できませんでした"); }
    finally { setBusy(false); }
  }
  return <fieldset className="order-schedule-row" disabled={disabled || busy}>
    <legend>祝日の確認</legend>
    <p className="order-field-hint">祝日は稼働しない「休業日」と別です。候補の正確性は将来の法改正などで変わるため、確認してください。変更は報酬と請求で共有する祝日一覧に記録されます。</p>
    <button type="button" className="order-action-button is-add" disabled={!valid} onClick={() => void load()}>祝日一覧を確認</button>
    {rows && loadedPeriod === key && <>
      <ul>{rows.map((row) => <li key={row.day}>{row.day} {row.name || "名称なし"} {row.is_holiday ? "祝日" : "祝日から除外"}
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => void update(row.day, !row.is_holiday, row.name, row.revision)}>{row.is_holiday ? "祝日から外す" : "祝日に戻す"}</button></li>)}</ul>
      <label>祝日を追加<input type="date" min={from} max={to} value={day} onChange={(event) => setDay(event.target.value)} /></label>
      <label>名称<input value={name} maxLength={200} onChange={(event) => setName(event.target.value)} /></label>
      <button type="button" className="btn btn-ghost" disabled={!day || day < from || day > to} onClick={() => void update(day, true, name, rows.find((row) => row.day === day)?.revision ?? 0)}>共通の祝日一覧に追加</button>
      <button type="button" className="btn btn-primary" onClick={() => void apply()}>この一覧を確認して依頼書に反映</button>
    </>}
    {message && <p role="status">{message}</p>}
  </fieldset>;
}
