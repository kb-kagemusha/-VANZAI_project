import holidayJp from "@holiday-jp/holiday_jp";

import type { WorkerAvailabilityPreference } from "../../types/api";

export const availabilityStatusOptions = [
  { value: "available_all_day", label: "稼働OK（1日）", shortLabel: "終日OK" },
  { value: "available_after_15", label: "稼働OK（15時〜）", shortLabel: "15時〜" },
  { value: "unavailable", label: "稼働不可", shortLabel: "不可" },
  { value: "consult_required", label: "稼働はできなくはないので事前相談して", shortLabel: "要相談" },
] as const;

export const weekdayPreferenceOptions = [
  { value: "0", label: "日曜" },
  { value: "1", label: "月曜" },
  { value: "2", label: "火曜" },
  { value: "3", label: "水曜" },
  { value: "4", label: "木曜" },
  { value: "5", label: "金曜" },
  { value: "6", label: "土曜" },
] as const;

export type AvailabilityStatusValue = (typeof availabilityStatusOptions)[number]["value"];
export type WeekdayPreferenceKey = (typeof weekdayPreferenceOptions)[number]["value"];

export interface StaffAvailabilityPreferences {
  weeklyDefaultStatuses: Partial<Record<WeekdayPreferenceKey, AvailabilityStatusValue>>;
  holidayDefaultStatus: AvailabilityStatusValue | "";
  autoApplyEnabled: boolean;
}

export interface AvailabilityTemplateDetail {
  status: AvailabilityStatusValue | "";
  reason: string;
  source: "weekday" | "holiday" | null;
}

const defaultPreferences: StaffAvailabilityPreferences = {
  weeklyDefaultStatuses: {},
  holidayDefaultStatus: "",
  autoApplyEnabled: true,
};

const weekdayLabelByKey: Record<WeekdayPreferenceKey, string> = {
  "0": "日曜",
  "1": "月曜",
  "2": "火曜",
  "3": "水曜",
  "4": "木曜",
  "5": "金曜",
  "6": "土曜",
};

function createLocalDate(dateValue: string) {
  const [year, month, day] = dateValue.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function isAvailabilityStatusValue(value: unknown): value is AvailabilityStatusValue {
  return availabilityStatusOptions.some((option) => option.value === value);
}

function normalizeWeekdayPreferenceKey(value: string): WeekdayPreferenceKey | null {
  return weekdayPreferenceOptions.some((option) => option.value === value) ? (value as WeekdayPreferenceKey) : null;
}

export function getDefaultStaffAvailabilityPreferences(): StaffAvailabilityPreferences {
  return defaultPreferences;
}

export function normalizeStaffAvailabilityPreferences(
  preferences: Partial<WorkerAvailabilityPreference> | null | undefined,
): StaffAvailabilityPreferences {
  const weeklyDefaultStatuses: Partial<Record<WeekdayPreferenceKey, AvailabilityStatusValue>> = {};

  for (const [key, value] of Object.entries(preferences?.weekly_default_statuses ?? {})) {
    const normalizedKey = normalizeWeekdayPreferenceKey(key);
    if (normalizedKey && isAvailabilityStatusValue(value)) {
      weeklyDefaultStatuses[normalizedKey] = value;
    }
  }

  return {
    weeklyDefaultStatuses,
    holidayDefaultStatus: isAvailabilityStatusValue(preferences?.holiday_default_status) ? preferences.holiday_default_status : "",
    autoApplyEnabled: preferences?.auto_apply_enabled ?? defaultPreferences.autoApplyEnabled,
  };
}

export function toWorkerAvailabilityPreferencePayload(preferences: StaffAvailabilityPreferences) {
  const weeklyDefaultStatuses: Record<string, string> = {};

  for (const [key, value] of Object.entries(preferences.weeklyDefaultStatuses)) {
    if (value && isAvailabilityStatusValue(value)) {
      weeklyDefaultStatuses[key] = value;
    }
  }

  return {
    weekly_default_statuses: weeklyDefaultStatuses,
    holiday_default_status: preferences.holidayDefaultStatus || null,
    auto_apply_enabled: preferences.autoApplyEnabled,
  };
}

export function getAvailabilityTemplateDetail(
  dateValue: string,
  preferences: StaffAvailabilityPreferences,
): AvailabilityTemplateDetail {
  if (!preferences.autoApplyEnabled) {
    return { status: "", reason: "", source: null };
  }

  const currentDate = createLocalDate(dateValue);
  const weekdayKey = String(currentDate.getDay()) as WeekdayPreferenceKey;

  if (holidayJp.isHoliday(currentDate) && preferences.holidayDefaultStatus) {
    return {
      status: preferences.holidayDefaultStatus,
      reason: "祝日の基本設定",
      source: "holiday",
    };
  }

  const weekdayStatus = preferences.weeklyDefaultStatuses[weekdayKey] ?? "";
  if (weekdayStatus) {
    return {
      status: weekdayStatus,
      reason: `${weekdayLabelByKey[weekdayKey]}の基本設定`,
      source: "weekday",
    };
  }

  return { status: "", reason: "", source: null };
}

export function getAvailabilityTemplateStatus(dateValue: string, preferences: StaffAvailabilityPreferences): AvailabilityStatusValue | "" {
  return getAvailabilityTemplateDetail(dateValue, preferences).status;
}