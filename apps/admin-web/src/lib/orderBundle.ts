/**
 * ダブルヘッダー（同じ日の2件を1件の依頼としてまとめて送る。DEC-148）の画面用の補助。
 * 判定はサーバー（src/domain/order_bundle.py）と同じ。保存・確定の可否はサーバーが決める。
 */
import { newWorkGroup, syncSchedule, emptySchedule, type OrderSchedule } from "./orderSchedule";
import { formatWorkDateRange, type OrderDocumentSections } from "./orderRequestFormat";
import type { OrderRequestWrite } from "../types/orderRequest";

export interface BundleLegState {
  form: OrderRequestWrite;
  sections: OrderDocumentSections;
}

export interface LegSummary {
  date: string;
  start: string;
  end: string;
  gathering: string;
  endNextDay: boolean;
  amount: string;
  unit: "day" | "hour";
  singleDay: boolean;
}

export function legSummary(sections: OrderDocumentSections): LegSummary {
  const groups = sections.schedule?.work_groups ?? [];
  const group = groups[0];
  const rate = sections.schedule?.rate_groups?.[0];
  return {
    date: group?.from ?? "",
    start: group?.start_time ?? "",
    end: group?.end_time ?? "",
    gathering: group?.gathering_time ?? "",
    endNextDay: Boolean(group?.end_next_day),
    amount: rate?.amount ?? "",
    unit: (rate?.unit as "day" | "hour") ?? "day",
    singleDay: groups.length <= 1 && (!group || group.date_mode === "single"),
  };
}

function baseSchedule(sections: OrderDocumentSections): OrderSchedule {
  const schedule = sections.schedule ?? syncSchedule({ ...emptySchedule(), work_groups: [newWorkGroup()] });
  return schedule.work_groups.length ? schedule : syncSchedule({ ...schedule, work_groups: [newWorkGroup()] });
}

/** 1件分の時間・単価を直す（1日ごとの1行を前提にする）。 */
export function patchLeg(sections: OrderDocumentSections, patch: Partial<Pick<LegSummary, "start" | "end" | "gathering" | "endNextDay" | "amount" | "unit">>): OrderDocumentSections {
  const schedule = baseSchedule(sections);
  const [group, ...rest] = schedule.work_groups;
  const nextGroup = {
    ...group,
    ...(patch.start !== undefined ? { start_time: patch.start } : {}),
    ...(patch.end !== undefined ? { end_time: patch.end } : {}),
    ...(patch.gathering !== undefined ? { gathering_time: patch.gathering } : {}),
    ...(patch.endNextDay !== undefined ? { end_next_day: patch.endNextDay } : {}),
  };
  let next = syncSchedule({ ...schedule, work_groups: [nextGroup, ...rest] });
  if (patch.amount !== undefined || patch.unit !== undefined) {
    next = { ...next, rate_groups: next.rate_groups.map((rate, index) => index === 0 ? { ...rate, ...(patch.amount !== undefined ? { amount: patch.amount } : {}), ...(patch.unit !== undefined ? { unit: patch.unit } : {}) } : rate) };
  }
  return { ...sections, schedule: next };
}

/** 2件共通の稼働日（1日）を入れる。期間・毎週は使わず「1日ごと」の1行にする。 */
export function setLegDate(state: BundleLegState, day: string): BundleLegState {
  const schedule = baseSchedule(state.sections);
  const [group] = schedule.work_groups;
  const nextGroup = { ...group, date_mode: "single" as const, from: day, to: day, excluded_dates: [] };
  const next = syncSchedule({ ...schedule, work_groups: [nextGroup] });
  return {
    form: { ...state.form, work_date_label: day ? formatWorkDateRange(day, day) : "" },
    sections: { ...state.sections, workPeriod: { from: day, to: day }, schedule: next },
  };
}

/** 2件で共通にする欄（区分・送付先・個人の不参加日・期限・追跡担当・稼働日）を、基準の件から写す。 */
export function alignShared(target: BundleLegState, source: BundleLegState): BundleLegState {
  const form: OrderRequestWrite = {
    ...target.form,
    kind: source.form.kind,
    worker_ids: source.form.worker_ids,
    recipient_absences: source.form.recipient_absences,
    follow_up_due_on: source.form.follow_up_due_on,
    follow_up_due_time: source.form.follow_up_due_time,
    tracker_user_id: source.form.tracker_user_id,
    assign_tracker_self: source.form.assign_tracker_self,
    allow_partial_accept: false,
    requires_operator_confirmation: false,
  };
  const day = legSummary(source.sections).date || source.sections.workPeriod?.from || "";
  return setLegDate({ form, sections: target.sections }, day);
}

export interface BundleCheck {
  complete: boolean;
  issues: string[];
  overlap: boolean;
  short: boolean;
  gapMinutes: number | null;
  /** 始まりの早い方の添字（0 か 1） */
  earlier: number;
}

function minutesOf(hm: string): number {
  const [h, m] = hm.split(":").map(Number);
  return h * 60 + m;
}

export function bundleCheck(first: OrderDocumentSections, second: OrderDocumentSections, travelMinutes: number): BundleCheck {
  const legs = [legSummary(first), legSummary(second)];
  const issues: string[] = [];
  legs.forEach((leg, index) => {
    if (!leg.singleDay) issues.push(`${index + 1}件目の稼働日は「1日ごと」の1日だけにしてください`);
  });
  if (legs[0].date && legs[1].date && legs[0].date !== legs[1].date) issues.push("1件目と2件目の稼働日を同じ日にしてください");
  const base = { complete: false, issues, overlap: false, short: false, gapMinutes: null, earlier: 0 };
  if (issues.length || !legs.every((leg) => leg.date && (leg.gathering || leg.start) && leg.end)) return base;
  const spans = legs.map((leg) => {
    const start = minutesOf(leg.gathering || leg.start);
    const end = minutesOf(leg.end) + (leg.endNextDay ? 24 * 60 : 0);
    return [start, end] as const;
  });
  const earlier = spans[0][0] <= spans[1][0] ? 0 : 1;
  const gap = spans[1 - earlier][0] - spans[earlier][1];
  return { complete: true, issues, overlap: gap < 0, short: gap >= 0 && gap < travelMinutes, gapMinutes: gap, earlier };
}

/** 報酬の合計（2件の日給の和）。片方でも時給・未入力なら null。 */
export function bundlePayTotal(first: OrderDocumentSections, second: OrderDocumentSections): { total: number | null; hourly: boolean } {
  const legs = [legSummary(first), legSummary(second)];
  const hourly = legs.some((leg) => leg.unit === "hour");
  if (hourly || legs.some((leg) => !leg.amount)) return { total: null, hourly };
  return { total: legs.reduce((sum, leg) => sum + Number(leg.amount), 0), hourly: false };
}
