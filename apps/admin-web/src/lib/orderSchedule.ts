import { formatWorkDateRange } from "./orderRequestFormat";

export interface DateGroup {
  id: string; date_mode: "single" | "range" | "weekly"; from: string; to: string; weekdays?: number[]; holiday_mode?: "include" | "exclude"; holiday_dates?: string[]; holiday_review_from?: string; holiday_review_to?: string;
  /** 「毎週」の新しい規則（曜日と祝日のボタン）。無い・legacy は旧規則（holiday_mode）のまま。 */
  weekly_rule?: "legacy" | "v2";
  /** v2：「祝日」ボタンを押した行。祝日はいつもこの行の条件で上書きする。 */
  holiday_selected?: boolean;
  /** v2：他の行の「祝日」に上書きされ、この行では稼働しない祝日（syncSchedule が導出。サーバーも同じ規則で導出する）。 */
  holiday_skip?: string[];
  /** v2：期間を区切る行だけ true。false の行は全体の稼働期間の全部が対象。 */
  custom_range?: boolean;
}
export interface WorkGroup extends DateGroup {
  start_time: string; end_time: string; end_next_day: boolean; gathering_time: string; notes: string;
  /** 期間の中の共通の休業日（DEC-065）。旧データには無い。 */
  excluded_dates?: string[];
}
export interface RateGroup extends DateGroup {
  work_group_id: string | null; amount: string; unit: "day" | "hour";
  lunch_included: boolean; transport_included: boolean; lunch_note: string; transport_note: string; notes: string;
}
export interface OrderSchedule { version: 1; work_groups: WorkGroup[]; rates_follow_work: boolean; rate_groups: RateGroup[] }

export function emptySchedule(): OrderSchedule {
  return { version: 1, work_groups: [], rates_follow_work: true, rate_groups: [] };
}
export function newWorkGroup(): WorkGroup {
  return { id: crypto.randomUUID(), date_mode: "single", from: "", to: "", start_time: "09:00", end_time: "17:00", end_next_day: false, gathering_time: "", notes: "", excluded_dates: [] };
}
export function newRateGroup(group?: DateGroup): RateGroup {
  return { id: crypto.randomUUID(), date_mode: group?.date_mode ?? "single", from: group?.from ?? "", to: group?.to ?? "", work_group_id: group?.id ?? null,
    amount: "", unit: "day", lunch_included: true, transport_included: true, lunch_note: "", transport_note: "", notes: "" };
}
/** 全体の休業日を、稼働日の詳細（期間）ごとの休業日に配る（サーバーの apply_period_holidays と同じ）。 */
export function applyPeriodHolidays(schedule: OrderSchedule, holidays: string[]): OrderSchedule {
  const days = new Set(holidays);
  return { ...schedule, work_groups: schedule.work_groups.map((group) => ({
    ...group,
    excluded_dates: group.date_mode !== "single" && group.from && group.to ? [...days].filter((d) => d >= group.from && d <= group.to).sort() : [],
  })) };
}
/** 休業日に重なっている「1日ごと」の稼働日（保存できないので、その場で知らせる）。 */
export function singleDaysOnHolidays(schedule: OrderSchedule, holidays: string[]): string[] {
  const days = new Set(holidays);
  return schedule.work_groups.filter((g) => g.date_mode === "single" && g.from && days.has(g.from)).map((g) => g.from);
}
/** v2：「祝日」を押した別の行が同じ祝日を使うとき、曜日の行ではその祝日を稼働にしない（サーバーの _derive_holiday_skip と同じ）。 */
export function deriveHolidaySkip<T extends DateGroup>(groups: T[]): T[] {
  const isV2 = (group: DateGroup) => group.date_mode === "weekly" && group.weekly_rule === "v2";
  const selectors = groups.filter((group) => isV2(group) && group.holiday_selected && group.from && group.to);
  return groups.map((group) => {
    if (!isV2(group)) return group;
    const skip = group.holiday_selected || !group.from || !group.to ? [] : (group.holiday_dates ?? []).filter((day) =>
      day >= group.from && day <= group.to && (group.weekdays ?? []).includes(weekdayOf(day))
      && selectors.some((other) => other !== group && other.from <= day && day <= other.to && (other.holiday_dates ?? []).includes(day))).sort();
    const before = group.holiday_skip ?? [];
    const same = skip.length === before.length && skip.every((day, k) => day === before[k]);
    return same ? group : { ...group, holiday_skip: skip };
  });
}
function weekdayOf(iso: string): number {
  return (new Date(`${iso}T00:00:00Z`).getUTCDay() + 6) % 7;
}
/** 期間を区切っていない v2 の「毎週」の行は、全体の稼働期間の全部を対象にする。期間が変わった行は祝日の確認をやり直す。 */
export function applyWeeklyPeriod(schedule: OrderSchedule, from: string, to: string): OrderSchedule {
  let changed = false;
  const work_groups = schedule.work_groups.map((group) => {
    if (group.date_mode !== "weekly" || group.weekly_rule !== "v2" || group.custom_range) return group;
    if (group.from === from && group.to === to) return group;
    changed = true;
    return { ...group, from, to, holiday_dates: [], holiday_skip: [], holiday_review_from: "", holiday_review_to: "" };
  });
  return changed ? { ...schedule, work_groups } : schedule;
}
export function syncSchedule(schedule: OrderSchedule): OrderSchedule {
  const work_groups = deriveHolidaySkip(schedule.work_groups);
  const base = work_groups.every((group, k) => group === schedule.work_groups[k]) ? schedule : { ...schedule, work_groups };
  if (!base.rates_follow_work) return base;
  return { ...base, rate_groups: base.work_groups.map((group) => {
    const existing = base.rate_groups.find((rate) => rate.work_group_id === group.id)
      ?? base.rate_groups.find((rate) => !rate.work_group_id && rate.from === group.from && rate.to === group.to && rate.date_mode === group.date_mode);
    const weeklyV2 = group.date_mode === "weekly" && group.weekly_rule === "v2";
    return { ...(existing ?? newRateGroup(group)), work_group_id: group.id, date_mode: group.date_mode, from: group.from, to: group.to, weekdays: group.weekdays ?? [], holiday_mode: group.holiday_mode ?? "exclude", holiday_dates: group.holiday_dates ?? [], holiday_review_from: group.holiday_review_from ?? "", holiday_review_to: group.holiday_review_to ?? "",
      ...(weeklyV2 ? { weekly_rule: "v2" as const, holiday_selected: Boolean(group.holiday_selected), holiday_skip: group.holiday_skip ?? [], custom_range: Boolean(group.custom_range) } : {}) };
  }) };
}
function shortDate(iso: string): string {
  const [, month, day] = iso.split("-").map(Number);
  return `${month}月${day}日`;
}
export function dateGroupLabel(group: DateGroup & { excluded_dates?: string[] }): string {
  // 休業日は本文の「■休業日」に1回だけ出す（0.48.7。ここに括弧書きで重ねない）
  const dates = formatWorkDateRange(group.from, group.date_mode !== "single" ? group.to : "");
  if (group.date_mode !== "weekly") return dates;
  const names = ["月", "火", "水", "木", "金", "土", "日"];
  const labels = (group.weekdays ?? []).map((d) => names[d]).join("・");
  if (group.weekly_rule === "v2") return `${dates} ${group.holiday_selected ? (labels ? `毎週${labels}・祝日` : "祝日") : `毎週${labels}`}`;
  return `${dates} 毎週${labels}（祝日を${group.holiday_mode === "include" ? "含む" : "除く"}）`;
}
/** 勤務グループの実勤務日（共通の休業日を除く。サーバーの expand_work_days と同じ規則）。 */
export function groupWorkDates(group: WorkGroup): string[] {
  if (!group.from) return [];
  const to = group.date_mode !== "single" ? group.to : group.from;
  if (!to || to < group.from) return [];
  const excluded = new Set(group.date_mode !== "single" ? group.excluded_dates ?? [] : []);
  const holidays = new Set(group.holiday_dates ?? []);
  const skip = new Set(group.holiday_skip ?? []);
  const days: string[] = [];
  const cursor = new Date(`${group.from}T00:00:00Z`);
  const last = new Date(`${to}T00:00:00Z`);
  let visited = 0;
  while (cursor <= last && visited < 3661) {
    const iso = cursor.toISOString().slice(0, 10);
    const weekday = (cursor.getUTCDay() + 6) % 7;
    const regular = (group.weekdays ?? []).includes(weekday);
    const selected = group.date_mode !== "weekly" || (group.weekly_rule === "v2"
      ? (regular && !skip.has(iso)) || (Boolean(group.holiday_selected) && holidays.has(iso))
      : group.holiday_mode === "include" ? regular || holidays.has(iso) : regular && !holidays.has(iso));
    if (!excluded.has(iso) && selected) days.push(iso);
    cursor.setUTCDate(cursor.getUTCDate() + 1);
    visited++;
  }
  return days;
}
/** 依頼書全体の実勤務日（重複なし・昇順）。 */
export function scheduleWorkDates(schedule: OrderSchedule | undefined): string[] {
  if (!schedule) return [];
  return [...new Set(schedule.work_groups.flatMap(groupWorkDates))].sort();
}
export function scheduleDateLabel(schedule: OrderSchedule): string {
  return [...schedule.work_groups].sort((a, b) => a.from.localeCompare(b.from)).map(dateGroupLabel).filter(Boolean).join("\n");
}
export function scheduleHours(schedule: OrderSchedule): string {
  return [...schedule.work_groups].sort((a, b) => a.from.localeCompare(b.from)).map((group) => [
    dateGroupLabel(group),
    group.gathering_time ? `集合：${group.gathering_time}` : "",
    group.start_time || group.end_time ? `稼働：${group.start_time}～${group.end_next_day ? "翌日 " : ""}${group.end_time}` : "",
    group.notes.trim(),
  ].filter(Boolean).join("\n")).join("\n\n");
}
export function scheduleFees(schedule: OrderSchedule): string {
  return [...syncSchedule(schedule).rate_groups].sort((a, b) => a.from.localeCompare(b.from)).map((group) => [
    dateGroupLabel(group),
    group.amount ? `${group.unit === "hour" ? "時給" : "日給"}：¥${Number(group.amount).toLocaleString("ja-JP", { maximumFractionDigits: 2 })}（税抜）` : "",
    group.lunch_included ? "昼食代：込み" : `昼食代：別途${group.lunch_note ? `（${group.lunch_note.trim()}）` : ""}`,
    group.transport_included ? "交通費：込み" : `交通費：別途${group.transport_note ? `（${group.transport_note.trim()}）` : ""}`,
    group.notes.trim(),
  ].filter(Boolean).join("\n")).join("\n\n");
}

/** 保存済みデータだけを復元する。自由文から日付・報酬を推測しない。 */
export function scheduleFromStored(value: unknown): OrderSchedule | undefined {
  if (!value || typeof value !== "object") return undefined;
  const schedule = value as OrderSchedule;
  if (schedule.version !== 1 || !Array.isArray(schedule.work_groups) || !Array.isArray(schedule.rate_groups) || typeof schedule.rates_follow_work !== "boolean") return undefined;
  return schedule;
}

/** 日付の集合を「11/1〜11/3、11/5」の形にする（連続する日はまとめる）。 */
export function compactDateList(days: string[]): string {
  const sorted = Array.from(new Set(days)).sort();
  const label = (day: string) => {
    const [, month, date] = day.split("-");
    return `${Number(month)}/${Number(date)}`;
  };
  const next = (day: string) => {
    const value = new Date(`${day}T00:00:00Z`);
    value.setUTCDate(value.getUTCDate() + 1);
    return value.toISOString().slice(0, 10);
  };
  const parts: string[] = [];
  let start = "";
  let prev = "";
  for (const day of sorted) {
    if (start && next(prev) === day) {
      prev = day;
      continue;
    }
    if (start) parts.push(start === prev ? label(start) : `${label(start)}〜${label(prev)}`);
    start = day;
    prev = day;
  }
  if (start) parts.push(start === prev ? label(start) : `${label(start)}〜${label(prev)}`);
  return parts.join("、");
}

/** 「毎週」の重なり・漏れ。重なりは保存前に直してもらい、漏れは「稼働しない」と確認してもらう。 */
export interface WeeklyIssues { overlaps: string[]; gaps: string[] }
const WEEKDAY_NAMES = ["月", "火", "水", "木", "金", "土", "日"];
export function weeklyScheduleIssues(schedule: OrderSchedule, periodFrom: string, periodTo: string, closedDates: string[] = []): WeeklyIssues {
  const issues: WeeklyIssues = { overlaps: [], gaps: [] };
  const rows = schedule.work_groups.map((group, index) => ({ group, index })).filter(({ group }) => group.date_mode === "weekly" && group.weekly_rule === "v2" && group.from && group.to);
  for (let i = 0; i < rows.length; i++) {
    for (let j = i + 1; j < rows.length; j++) {
      const a = rows[i].group;
      const b = rows[j].group;
      if (a.from > b.to || b.from > a.to) continue;
      const shared = (a.weekdays ?? []).filter((day) => (b.weekdays ?? []).includes(day)).map((day) => WEEKDAY_NAMES[day]);
      if (a.holiday_selected && b.holiday_selected) shared.push("祝日");
      if (shared.length) issues.overlaps.push(`稼働日の詳細${rows[i].index + 1}と${rows[j].index + 1}で「${shared.join("・")}」が重なっています。同じ曜日・祝日は1つの行だけで押してください。`);
    }
  }
  const complete = schedule.work_groups.length > 0 && schedule.work_groups.every((group) => group.from && group.to);
  if (rows.length && complete && periodFrom && periodTo && periodFrom <= periodTo) {
    const worked = new Set(scheduleWorkDates(schedule));
    // 休業日（全体の設定と、各行に配られた休業日）は稼働しない日として意図されているので、漏れに数えない
    const closed = new Set([...closedDates, ...schedule.work_groups.flatMap((group) => group.excluded_dates ?? [])]);
    const holidays = new Set(rows.flatMap(({ group }) => group.holiday_dates ?? []));
    const missing = new Set<string>();
    const cursor = new Date(`${periodFrom}T00:00:00Z`);
    const last = new Date(`${periodTo}T00:00:00Z`);
    for (let visited = 0; cursor <= last && visited < 3661; visited++) {
      const iso = cursor.toISOString().slice(0, 10);
      cursor.setUTCDate(cursor.getUTCDate() + 1);
      if (worked.has(iso) || closed.has(iso)) continue;
      missing.add(WEEKDAY_NAMES[weekdayOf(iso)]);
      if (holidays.has(iso)) missing.add("祝日");
    }
    if (missing.size) {
      const ordered = [...WEEKDAY_NAMES, "祝日"].filter((name) => missing.has(name));
      issues.gaps.push(`${ordered.join("・")}に当たる日の条件がありません。この日は稼働しない日になります。`);
    }
  }
  return issues;
}
