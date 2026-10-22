/**
 * 月カレンダーの共通部品（統合計画 §3）。共有するのは「月の切り替え」「日付のマス」「日本時間の日付の扱い」だけ。
 * マスの中身・選択・人数の表示は、使う画面が renderDay で決める。
 */
import type { ReactNode } from "react";

const WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"];

export function monthOf(day: string): string {
  return day.slice(0, 7);
}

export function shiftMonth(month: string, delta: number): string {
  const [year, mon] = month.split("-").map(Number);
  const value = new Date(Date.UTC(year, mon - 1 + delta, 1));
  return `${value.getUTCFullYear()}-${String(value.getUTCMonth() + 1).padStart(2, "0")}`;
}

export function todayInTokyo(): string {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Tokyo" }).format(new Date());
}

/** 月のマス（前後の空白を含む7列）。null は空白。 */
export function monthCells(month: string): Array<string | null> {
  const [year, mon] = month.split("-").map(Number);
  const first = new Date(Date.UTC(year, mon - 1, 1));
  const days = new Date(Date.UTC(year, mon, 0)).getUTCDate();
  const cells: Array<string | null> = Array.from({ length: first.getUTCDay() }, () => null);
  for (let d = 1; d <= days; d += 1) cells.push(`${month}-${String(d).padStart(2, "0")}`);
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

export function MonthCalendar({
  month,
  onMonthChange,
  minMonth,
  maxMonth,
  renderDay,
  className,
}: {
  month: string;
  onMonthChange: (month: string) => void;
  minMonth?: string;
  maxMonth?: string;
  renderDay: (day: string) => ReactNode;
  className?: string;
}) {
  const [year, mon] = month.split("-");
  const canPrev = !minMonth || shiftMonth(month, -1) >= minMonth;
  const canNext = !maxMonth || shiftMonth(month, 1) <= maxMonth;
  return (
    <div className={`month-calendar${className ? ` ${className}` : ""}`}>
      <div className="month-calendar-head">
        <button type="button" className="month-calendar-nav" disabled={!canPrev} onClick={() => onMonthChange(shiftMonth(month, -1))} aria-label="前の月">‹</button>
        <strong>{Number(year)}年{Number(mon)}月</strong>
        <button type="button" className="month-calendar-nav" disabled={!canNext} onClick={() => onMonthChange(shiftMonth(month, 1))} aria-label="次の月">›</button>
      </div>
      <div className="month-calendar-grid" role="grid">
        {WEEKDAYS.map((w, i) => <div key={w} className={`month-calendar-weekday${i === 0 ? " is-sun" : i === 6 ? " is-sat" : ""}`}>{w}</div>)}
        {monthCells(month).map((day, index) => (
          <div key={day ?? `blank-${index}`} className="month-calendar-cell" role="gridcell">
            {day ? renderDay(day) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
