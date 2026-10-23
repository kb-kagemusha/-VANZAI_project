import { apiFetch } from "./api/client";

export type AttendanceNote = {
  id: string; schedule_entry_id: string; series_id: string; worker_id: string; work_date: string;
  project_name: string; worker_name: string; is_test: boolean; kind: "late" | "cancel";
  cause: "personal" | "weather" | "other"; late_minutes: number | null; reason: string;
  reported_by: string; actor_name: string; created_at: string; voided_at: string | null; void_reason: string | null;
  summary: string; payment_note: string;
};
export type AttendanceNoteBody = Pick<AttendanceNote, "schedule_entry_id" | "kind" | "cause" | "late_minutes" | "reason" | "reported_by">;
export type AttendanceNotePage = { items: AttendanceNote[]; total: number; limit: number; offset: number };
export const getAttendanceNotes = (params: { period_key: string; worker_id?: string; series_id?: string; is_test?: boolean; include_voided?: boolean; offset?: number }) =>
  apiFetch<AttendanceNotePage>("/api/attendance-notes", undefined, params);
export const getAttendanceEvents = (period_key: string, is_test: boolean) =>
  apiFetch<{ items: { series_id: string; project_name: string }[] }>("/api/attendance-notes/events", undefined, { period_key, is_test });
export const getAttendanceSchedules = (series_id: string, day: string, is_test: boolean) =>
  apiFetch<{ items: { id: string; worker_id: string; worker_name: string; start_time: string | null; end_time: string | null; status: string }[] }>("/api/attendance-notes/schedules", undefined, { series_id, day, is_test });
export const recordAttendanceNote = (body: AttendanceNoteBody) =>
  apiFetch<AttendanceNote>("/api/attendance-notes", { method: "POST", body: JSON.stringify(body) });
export const voidAttendanceNote = (id: string, reason: string) =>
  apiFetch<AttendanceNote>(`/api/attendance-notes/${id}/void`, { method: "POST", body: JSON.stringify({ reason }) });
export const getAttendancePaymentSummary = (period_key: string) =>
  apiFetch<{ total: number; payouts: Record<string, { worker_id: string; count: number }> }>("/api/attendance-notes/payment-summary", undefined, { period_key });
