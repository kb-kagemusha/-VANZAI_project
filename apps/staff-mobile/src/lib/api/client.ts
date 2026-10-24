import type {
  ActualListItem,
  AssignmentListItem,
  AttendanceRecord,
  AuthUser,
  ExpenseListItem,
  ExpenseSubmissionResponse,
  PageResponse,
  TokenResponse,
  WorkerAvailabilityListItem,
  WorkerAvailabilityPreference,
  WorkerNoticeItem,
  WorkerNoticeListResponse,
} from "../../types/api";

function resolveApiBaseUrl(): string {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }

  const { protocol, hostname } = window.location;
  if (hostname === "vanzai-portal.com" || hostname === "www.vanzai-portal.com" || hostname === "staff.vanzai-portal.com") {
    return `${protocol}//api.vanzai-portal.com`;
  }

  return "";
}

const API_BASE_URL = resolveApiBaseUrl();
const ACCESS_TOKEN_KEY = "vanzai.staff.access_token";
const REFRESH_TOKEN_KEY = "vanzai.staff.refresh_token";
const ACCESS_COOKIE = "vanzai_staff_access";
const REFRESH_COOKIE = "vanzai_staff_refresh";
const ACCESS_COOKIE_MAX_AGE_SECONDS = 60 * 30;
const REFRESH_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 7;

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin);

  Object.entries(params || {}).forEach(([key, value]) => {
    if (value === undefined || value === "") {
      return;
    }
    url.searchParams.set(key, String(value));
  });

  return API_BASE_URL ? url.toString() : `${path}${url.search}`;
}

async function readResponse(response: Response): Promise<unknown> {
  // 204/205 はボディなし
  if (response.status === 204 || response.status === 205) {
    return null;
  }
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const text = await response.text();
    return text ? JSON.parse(text) : null;
  }

  const text = await response.text();
  return text ? { message: text } : null;
}

function writeCookie(name: string, value: string, maxAgeSeconds: number) {
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${name}=${encodeURIComponent(value)}; Max-Age=${maxAgeSeconds}; Path=/; SameSite=Lax${secure}`;
}

function clearCookie(name: string) {
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${name}=; Max-Age=0; Path=/; SameSite=Lax${secure}`;
}

function readCookie(name: string): string | null {
  const prefix = `${name}=`;
  for (const part of document.cookie.split("; ")) {
    if (part.startsWith(prefix)) {
      return decodeURIComponent(part.slice(prefix.length));
    }
  }
  return null;
}

function readPersistedToken(storageKey: string, cookieName: string): string | null {
  const fromStorage = window.localStorage.getItem(storageKey);
  if (fromStorage) {
    return fromStorage;
  }
  const fromCookie = readCookie(cookieName);
  if (fromCookie) {
    window.localStorage.setItem(storageKey, fromCookie);
    return fromCookie;
  }
  return null;
}

function emitUnauthorized() {
  clearStoredAccessToken();
  window.dispatchEvent(new Event("vanzai:unauthorized"));
}

export function getStoredAccessToken(): string | null {
  return readPersistedToken(ACCESS_TOKEN_KEY, ACCESS_COOKIE);
}

export function getStoredRefreshToken(): string | null {
  return readPersistedToken(REFRESH_TOKEN_KEY, REFRESH_COOKIE);
}

export function setStoredSession(accessToken: string, refreshToken: string) {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  writeCookie(ACCESS_COOKIE, accessToken, ACCESS_COOKIE_MAX_AGE_SECONDS);
  writeCookie(REFRESH_COOKIE, refreshToken, REFRESH_COOKIE_MAX_AGE_SECONDS);
}

export function setStoredAccessToken(token: string) {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
  writeCookie(ACCESS_COOKIE, token, ACCESS_COOKIE_MAX_AGE_SECONDS);
}

export function clearStoredAccessToken() {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  clearCookie(ACCESS_COOKIE);
  clearCookie(REFRESH_COOKIE);
}

let refreshInFlight: Promise<boolean> | null = null;

async function performRefresh(): Promise<boolean> {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) {
    return false;
  }

  let response: Response;
  try {
    response = await fetch(buildUrl("/api/auth/refresh"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    return false;
  }

  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      clearStoredAccessToken();
    }
    return false;
  }

  const payload = (await readResponse(response)) as TokenResponse;
  if (!payload?.access_token || !payload?.refresh_token) {
    return false;
  }
  setStoredSession(payload.access_token, payload.refresh_token);
  return true;
}

export function refreshStoredSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = performRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

export async function ensurePersistentSession(): Promise<void> {
  if (getStoredRefreshToken()) {
    return;
  }
  const token = await apiFetch<TokenResponse>("/api/auth/session", { method: "POST" });
  setStoredSession(token.access_token, token.refresh_token);
}

async function fetchAuthorized(url: string, init?: RequestInit, retried = false): Promise<Response> {
  const headers = new Headers(init?.headers);
  const token = getStoredAccessToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, { ...init, headers });
  if (response.status !== 401 || retried) {
    if (response.status === 401) {
      emitUnauthorized();
    }
    return response;
  }

  if (!getStoredRefreshToken()) {
    emitUnauthorized();
    return response;
  }

  const refreshed = await refreshStoredSession();
  if (refreshed) {
    return fetchAuthorized(url, init, true);
  }
  if (!getStoredAccessToken() && !getStoredRefreshToken()) {
    emitUnauthorized();
  }
  return response;
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
  params?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  const headers = new Headers(init?.headers);

  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetchAuthorized(buildUrl(path, params), {
    ...init,
    headers,
  });
  const payload = await readResponse(response);

  if (!response.ok) {
    const message =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? String(payload.detail)
        : typeof payload === "object" && payload !== null && "message" in payload
          ? String(payload.message)
          : "API request failed";
    throw new ApiError(response.status, message, payload);
  }

  return payload as T;
}

async function downloadBinaryFile(path: string, fallbackFileName: string) {
  const response = await fetchAuthorized(buildUrl(path));

  if (!response.ok) {
    const payload = await readResponse(response);
    const message =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? String(payload.detail)
        : typeof payload === "object" && payload !== null && "message" in payload
          ? String(payload.message)
          : "ファイルのダウンロードに失敗しました";
    throw new ApiError(response.status, message, payload);
  }

  const blob = await response.blob();
  const contentDisposition = response.headers.get("content-disposition") || "";
  const matchedFileName = contentDisposition.match(/filename="?([^";]+)"?/i)?.[1];
  const fileName = matchedFileName || fallbackFileName;
  const objectUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(objectUrl);
}

export async function requestToken(username: string, password: string): Promise<TokenResponse> {
  const form = new URLSearchParams();
  form.set("username", username);
  form.set("password", password);

  const response = await fetch(buildUrl("/api/auth/token"), {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: form.toString(),
  });
  const payload = await readResponse(response);

  if (!response.ok) {
    const message =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? String(payload.detail)
        : "ログインに失敗しました";
    throw new ApiError(response.status, message, payload);
  }

  return payload as TokenResponse;
}

export function getCurrentUser(): Promise<AuthUser> {
  return apiFetch<AuthUser>("/api/auth/me");
}

export function changePassword(currentPassword: string, newPassword: string): Promise<{ message: string }> {
  return apiFetch<{ message: string }>("/api/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}

export function getAssignments(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<AssignmentListItem>>("/api/assignments", undefined, params);
}

export function updateAssignmentWorkerResponse(
  assignmentId: string,
  payload: { response_status: "accepted" | "declined"; note?: string },
) {
  return apiFetch<AssignmentListItem>(`/api/assignments/${assignmentId}/worker-response`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getActuals(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<ActualListItem>>("/api/actuals", undefined, params);
}

export function checkInAssignment(assignmentId: string, payload: { action_time?: string; notes?: string }) {
  return apiFetch<AttendanceRecord>(`/api/assignments/${assignmentId}/check-in`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function checkOutAssignment(
  assignmentId: string,
  payload: { action_time?: string; break_minutes_input?: number; notes?: string },
) {
  return apiFetch<AttendanceRecord>(`/api/assignments/${assignmentId}/check-out`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getExpenses(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<ExpenseListItem>>("/api/expenses", undefined, params);
}

export function submitExpense(formData: FormData) {
  return apiFetch<ExpenseSubmissionResponse>("/api/expenses", {
    method: "POST",
    body: formData,
  });
}

export function downloadExpenseReceipt(expenseId: string) {
  return downloadBinaryFile(`/api/expenses/${expenseId}/receipt`, `expense_receipt_${expenseId}`);
}

export function getWorkerAvailability(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<WorkerAvailabilityListItem>>("/api/worker-availability", undefined, params);
}

export function upsertWorkerAvailability(body: { availability_date: string; status: string; notes?: string }) {
  return apiFetch<WorkerAvailabilityListItem>("/api/worker-availability", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getWorkerAvailabilityPreferences() {
  return apiFetch<WorkerAvailabilityPreference>("/api/worker-availability/preferences");
}

export function upsertWorkerAvailabilityPreferences(body: {
  weekly_default_statuses: Record<string, string>;
  holiday_default_status?: string | null;
  auto_apply_enabled: boolean;
}) {
  return apiFetch<WorkerAvailabilityPreference>("/api/worker-availability/preferences", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

// ===========================
// Worker Notices
// ===========================

export function getWorkerNotices(params?: { unread_only?: boolean; offset?: number; limit?: number }) {
  return apiFetch<WorkerNoticeListResponse>("/api/worker/notices", undefined, params as Record<string, string | number | boolean | undefined>);
}

export function markNoticeRead(noticeId: string) {
  return apiFetch<void>(`/api/worker/notices/${noticeId}/read`, { method: "POST" });
}

export function respondToNotice(noticeId: string, response: "ok" | "ng") {
  return apiFetch<void>(`/api/worker/notices/${noticeId}/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ response }),
  });
}

// Push notifications
export function getVapidPublicKey(): Promise<{ public_key: string }> {
  return apiFetch<{ public_key: string }>("/api/worker/push/vapid-public-key");
}

export function registerPushSubscription(sub: {
  endpoint: string;
  p256dh: string;
  auth: string;
  user_agent_hash?: string;
}): Promise<void> {
  return apiFetch<void>("/api/worker/push/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(sub),
  });
}

export function unregisterPushSubscription(sub: {
  endpoint: string;
  p256dh: string;
  auth: string;
}): Promise<void> {
  return apiFetch<void>("/api/worker/push/subscribe", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(sub),
  });
}