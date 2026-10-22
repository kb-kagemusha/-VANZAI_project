import { formatWorkDateRange } from "./orderRequestFormat";

export interface DateGroup { id: string; date_mode: "single" | "range"; from: string; to: string }
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
  return { id: crypto.randomUUID(), date_mode: "single", from: "", to: "", start_time: "", end_time: "", end_next_day: false, gathering_time: "", notes: "", excluded_dates: [] };
}
export function newRateGroup(group?: DateGroup): RateGroup {
  return { id: crypto.randomUUID(), date_mode: group?.date_mode ?? "single", from: group?.from ?? "", to: group?.to ?? "", work_group_id: group?.id ?? null,
    amount: "", unit: "day", lunch_included: true, transport_included: true, lunch_note: "", transport_note: "", notes: "" };
}
export function syncSchedule(schedule: OrderSchedule): OrderSchedule {
  if (!schedule.rates_follow_work) return schedule;
  return { ...schedule, rate_groups: schedule.work_groups.map((group) => {
    const existing = schedule.rate_groups.find((rate) => rate.work_group_id === group.id)
      ?? schedule.rate_groups.find((rate) => !rate.work_group_id && rate.from === group.from && rate.to === group.to && rate.date_mode === group.date_mode);
    return { ...(existing ?? newRateGroup(group)), work_group_id: group.id, date_mode: group.date_mode, from: group.from, to: group.to };
  }) };
}
function shortDate(iso: string): string {
  const [, month, day] = iso.split("-").map(Number);
  return `${month}月${day}日`;
}
export function dateGroupLabel(group: DateGroup & { excluded_dates?: string[] }): string {
  const label = formatWorkDateRange(group.from, group.date_mode === "range" ? group.to : "");
  const excluded = group.date_mode === "range" && group.from && group.to ? (group.excluded_dates ?? []) : [];
  return excluded.length > 0 ? `${label}（休業日：${excluded.map(shortDate).join("、")}）` : label;
}
/** 勤務グループの実勤務日（共通の休業日を除く。サーバーの expand_work_days と同じ規則）。 */
export function groupWorkDates(group: WorkGroup): string[] {
  if (!group.from) return [];
  const to = group.date_mode === "range" ? group.to : group.from;
  if (!to || to < group.from) return [];
  const excluded = new Set(group.date_mode === "range" ? group.excluded_dates ?? [] : []);
  const days: string[] = [];
  const cursor = new Date(`${group.from}T00:00:00Z`);
  const last = new Date(`${to}T00:00:00Z`);
  while (cursor <= last && days.length < 400) {
    const iso = cursor.toISOString().slice(0, 10);
    if (!excluded.has(iso)) days.push(iso);
    cursor.setUTCDate(cursor.getUTCDate() + 1);
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
