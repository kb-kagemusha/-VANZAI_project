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
} from "../../types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const ACCESS_TOKEN_KEY = "vanzai.staff.access_token";

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

  return API_BASE_URL ? `${url.pathname}${url.search}` : `${path}${url.search}`;
}

async function readResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return text ? { message: text } : null;
}

function emitUnauthorized() {
  clearStoredAccessToken();
  window.dispatchEvent(new Event("vanzai:unauthorized"));
}

export function getStoredAccessToken(): string | null {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setStoredAccessToken(token: string) {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearStoredAccessToken() {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
  params?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  const headers = new Headers(init?.headers);
  const token = getStoredAccessToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(buildUrl(path, params), {
    ...init,
    headers,
  });
  const payload = await readResponse(response);

  if (!response.ok) {
    if (response.status === 401) {
      emitUnauthorized();
    }
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
  const headers = new Headers();
  const token = getStoredAccessToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(buildUrl(path), { headers });
  const payload = await readResponse(response);

  if (!response.ok) {
    if (response.status === 401) {
      emitUnauthorized();
    }
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