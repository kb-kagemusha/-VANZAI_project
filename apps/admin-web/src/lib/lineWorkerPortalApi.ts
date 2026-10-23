/**
 * 稼働者向けのWeb確認画面（統合計画 ②、DEC-084）のAPI。稼働者セッション（Bearer）で呼ぶ。
 * client.ts の publicApiFetch と同じ作り（管理画面のログインは使わない）。APIの置き場所の決め方も client.ts の resolveApiBaseUrl と同じ。
 */
import { ApiError } from "./api/client";

function apiBase(): string {
  if (import.meta.env.VITE_API_BASE_URL) return import.meta.env.VITE_API_BASE_URL;
  const { protocol, hostname } = window.location;
  if (hostname === "vanzai-portal.com" || hostname === "www.vanzai-portal.com" || hostname === "staff.vanzai-portal.com") {
    return `${protocol}//api.vanzai-portal.com`;
  }
  return "";
}

async function workerFetch<T>(token: string, path: string, init?: RequestInit, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${apiBase()}${path}`, window.location.origin);
  Object.entries(params ?? {}).forEach(([key, value]) => { if (value) url.searchParams.set(key, value); });
  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(url.toString(), { ...init, headers, cache: "no-store" });
  const type = response.headers.get("content-type") || "";
  const payload: unknown = type.includes("application/json") ? await response.json() : { message: await response.text() };
  if (!response.ok) {
    const detail = (payload as { detail?: unknown })?.detail;
    const message = detail && typeof detail === "object" && "message" in detail ? String((detail as { message: string }).message)
      : typeof detail === "string" ? detail : response.statusText;
    throw new ApiError(response.status, message || "通信に失敗しました。", payload);
  }
  return payload as T;
}

export type PortalEntry = {
  id: string;
  date: string;
  start_time: string | null;
  end_time: string | null;
  end_next_day: boolean;
  project_name: string;
  site_name: string;
  site_address: string | null;
  meeting_place: string | null;
  changing: boolean;
  is_test: boolean;
  delivery_id: string;
  document_number: string;
};

export type PortalDay = { date: string; entries: PortalEntry[] };

export type PortalEstimate = {
  /** 円未満を切り捨てた合計（文字列）。算出できた予定がなければ null */
  amount: string | null;
  work_days: number;
  counted_entries: number;
  excluded_hourly: number;
  excluded_unknown: number;
  separate_cost: boolean;
  formula_version: string;
  /** テストの依頼書の分（正式とは別。0.51.5）。テストの予定がなければ null */
  test?: Omit<PortalEstimate, "test"> | null;
};

export type PortalConfirmation = {
  kind: "unanswered" | "changing";
  delivery_id: string;
  document_number: string;
  version_no: number;
  project_name: string;
  site_name: string;
  first_date: string | null;
  last_date: string | null;
  offered_days: number;
  follow_up_due_on: string | null;
  is_test: boolean;
  can_pick: boolean;
  pdf_available: boolean;
};

export type PortalHome = {
  today: string;
  worker_name: string;
  month: string;
  month_days: PortalDay[];
  week: { from: string; to: string; days: PortalDay[] };
  estimate: PortalEstimate;
  confirmations: PortalConfirmation[];
  orders_enabled: boolean;
  fetched_at: string;
};

export type PortalOrder = {
  delivery_id: string;
  document_number: string;
  version_no: number;
  project_name: string;
  site_name: string;
  first_date: string;
  last_date: string;
  work_days: number;
  upcoming_days: number;
  acked_at: string | null;
  changing: boolean;
  newer_delivery_id: string | null;
  is_test: boolean;
  pdf_available: boolean;
};

export type PortalOrders = { today: string; since: string; items: PortalOrder[]; fetched_at: string };

export const getPortalHome = (token: string, month?: string) => workerFetch<PortalHome>(token, "/api/line/worker/home", undefined, month ? { month } : undefined);
export const getPortalOrders = (token: string) => workerFetch<PortalOrders>(token, "/api/line/worker/orders");
export const createPortalPdfLink = (token: string, deliveryId: string) =>
  workerFetch<{ url: string; expires_days: number }>(token, `/api/line/worker/deliveries/${encodeURIComponent(deliveryId)}/pdf-link`, { method: "POST" });
