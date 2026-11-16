import { useEffect, useState } from "react";
import { apiFetch } from "./api/client";

type Holiday = { day: string; is_holiday: boolean; revision: number; name?: string };
type HolidayState = { month: string; days: Set<string>; names: Map<string, string>; candidates: Set<string>; error: boolean };

const emptyHolidays = (): HolidayState => ({ month: "", days: new Set(), names: new Map(), candidates: new Set(), error: false });

/** Display Cabinet Office holidays by name, and library candidates only outside that coverage. */
export function useConfirmedHolidays(month: string) {
  const [state, setState] = useState<HolidayState>(emptyHolidays());
  useEffect(() => {
    if (!/^\d{4}-\d{2}$/.test(month)) return;
    let active = true;
    setState({ month, days: new Set(), names: new Map(), candidates: new Set(), error: false });
    const [year, number] = month.split("-").map(Number);
    const end = `${month}-${String(new Date(Date.UTC(year, number, 0)).getUTCDate()).padStart(2, "0")}`;
    apiFetch<Holiday[]>(`/api/order-requests/holiday-calendar?start=${month}-01&end=${end}`)
      .then((rows) => {
        if (!active) return;
        const holidays = rows.filter((row) => row.is_holiday);
        setState({
          month,
          days: new Set(holidays.map((row) => row.day)),
          names: new Map(holidays.filter((row) => row.name).map((row) => [row.day, row.name as string])),
          candidates: new Set(holidays.filter((row) => row.revision === 0).map((row) => row.day)),
          error: false,
        });
      })
      .catch(() => { if (active) setState({ month, days: new Set(), names: new Map(), candidates: new Set(), error: true }); });
    return () => { active = false; };
  }, [month]);
  return state.month === month ? state : { ...emptyHolidays(), month };
}

export function holidayMark(day: string, holidays: { names: Map<string, string>; candidates: Set<string> }) {
  const name = holidays.names.get(day) ?? "";
  if (holidays.candidates.has(day)) {
    const title = name ? `${name}（祝日候補・要確認）` : "祝日候補・要確認";
    return { label: `${day}（${name ? `${name}・祝日候補・要確認` : "祝日候補・要確認"}）`, title };
  }
  return name ? { label: `${day}（${name}）`, title: name } : { label: day, title: undefined };
}

export function orderDayColor(day: string, holidays: Set<string>) {
  const weekday = new Date(`${day}T00:00:00Z`).getUTCDay();
  return holidays.has(day) || weekday === 0 ? " is-holiday" : weekday === 6 ? " is-saturday" : "";
}
