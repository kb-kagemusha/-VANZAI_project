import { useState } from "react";
import { FormDialog } from "./FormDialog";
import { MonthCalendar, todayInTokyo } from "./MonthCalendar";
import { orderDayColor, useConfirmedHolidays } from "../lib/useConfirmedHolidays";
import "../styles/monthCalendar.css";

/** OS・ブラウザーの曜日設定によらず、依頼書の日付を月曜始まりで選ぶ。 */
export function OrderDatePicker({ value, onChange, disabled = false, min, max, label }: {
  value: string; onChange: (day: string) => void; disabled?: boolean; min?: string; max?: string; label: string;
}) {
  const [open, setOpen] = useState(false);
  const [month, setMonth] = useState("");
  const holidays = useConfirmedHolidays(open ? month : "");
  return <span className="order-date-picker">
    <button type="button" className="order-date-trigger" aria-label={label} aria-haspopup="dialog" disabled={disabled}
      onClick={() => { const initial = value || min || todayInTokyo(); setMonth((min && initial < min ? min : max && initial > max ? max : initial).slice(0, 7)); setOpen(true); }}>
      {value ? value.replace(/-/g, "/") : "日付を選択"}<span aria-hidden="true"> ▦</span>
    </button>
    {open ? <span onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); setOpen(false); } }}>
      <FormDialog open title={label} size="compact" onClose={() => setOpen(false)}>
        <MonthCalendar month={month} onMonthChange={setMonth} minMonth={min?.slice(0, 7)} maxMonth={max?.slice(0, 7)} renderDay={(day) => (
          <button type="button" className={`order-calendar-day${orderDayColor(day, holidays.days)}${day === value ? " is-selected" : ""}`} disabled={Boolean((min && day < min) || (max && day > max))}
            aria-label={day} aria-pressed={day === value} onClick={() => { onChange(day); setOpen(false); }}>{Number(day.slice(8))}</button>
        )} />
        {holidays.error && <p role="alert">祝日一覧を取得できませんでした。祝日の色を確認できません。</p>}
        <button type="button" className="btn btn-ghost" onClick={() => { onChange(""); setOpen(false); }}>日付をクリア</button>
      </FormDialog>
    </span> : null}
  </span>;
}
