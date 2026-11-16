import { useEffect, useState } from "react";
import { apiFetch } from "./api/client";

type Holiday = { day: string; is_holiday: boolean; revision: number };

/** Only reviewed calendar entries are displayed as holidays, never unconfirmed candidates. */
export function useConfirmedHolidays(month: string) {
  const [state, setState] = useState<{ month: string; days: Set<string>; error: boolean }>({ month: "", days: new Set(), error: false });
  useEffect(() => {
    if (!/^\d{4}-\d{2}$/.test(month)) return;
    let active = true;
    setState({ month, days: new Set(), error: false });
    const [year, number] = month.split("-").map(Number);
    const end = `${month}-${String(new Date(Date.UTC(year, number, 0)).getUTCDate()).padStart(2, "0")}`;
    apiFetch<Holiday[]>(`/api/order-requests/holiday-calendar?start=${month}-01&end=${end}`)
      .then((rows) => { if (active) setState({ month, days: new Set(rows.filter((row) => row.is_holiday && row.revision > 0).map((row) => row.day)), error: false }); })
      .catch(() => { if (active) setState({ month, days: new Set(), error: true }); });
    return () => { active = false; };
  }, [month]);
  return state.month === month ? state : { month, days: new Set<string>(), error: false };
}

export function orderDayColor(day: string, holidays: Set<string>) {
  const weekday = new Date(`${day}T00:00:00Z`).getUTCDay();
  return holidays.has(day) || weekday === 0 ? " is-holiday" : weekday === 6 ? " is-saturday" : "";
}
