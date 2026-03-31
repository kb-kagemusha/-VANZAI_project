import type {
  ActualListItem,
  AuditLogListItem,
  AssignmentListItem,
  CSVImportResponse,
  ClosingMutationResponse,
  ExpenseListItem,
  ImportBatchListItem,
  AuthUser,
  DashboardResponse,
  InvoiceListItem,
  InvoiceResponse,
  MonthlyBillingGenerateResponse,
  PageResponse,
  PayoutListItem,
  PayoutResponse,
  PriceOutsourceListItem,
  PriceRuleListItem,
  PriceSalesListItem,
  ProjectListItem,
  ShiftSlotListItem,
  TokenResponse,
} from "../../types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const ACCESS_TOKEN_KEY = "vanzai.admin.access_token";

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
    const message =
      typeof payload === "object" && payload !== null && "message" in payload
        ? String(payload.message)
        : typeof payload === "object" && payload !== null && "detail" in payload
          ? String(payload.detail)
          : response.statusText;

    if (response.status === 401) {
      emitUnauthorized();
    }

    throw new ApiError(response.status, message || "API request failed", payload);
  }

  return payload as T;
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

export function getDashboard(periodKey: string): Promise<DashboardResponse> {
  return apiFetch<DashboardResponse>("/api/dashboard", undefined, { period_key: periodKey });
}

export function getActuals(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<ActualListItem>>("/api/actuals", undefined, params);
}

export function getAssignments(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<AssignmentListItem>>("/api/assignments", undefined, params);
}

export function getInvoices(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<InvoiceListItem>>("/api/invoices", undefined, params);
}

export function getPayouts(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<PayoutListItem>>("/api/payouts", undefined, params);
}

export function searchAuditLogs(body: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<AuditLogListItem>>("/api/audit/search", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getProjects(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<ProjectListItem>>("/api/projects", undefined, params);
}

export function getShiftSlots(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<ShiftSlotListItem>>("/api/shift-slots", undefined, params);
}

export function getExpenses(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<ExpenseListItem>>("/api/expenses", undefined, params);
}

export function getPriceRules(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<PriceRuleListItem>>("/api/price-rules", undefined, params);
}

export function getPriceSales(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<PriceSalesListItem>>("/api/price-sales", undefined, params);
}

export function getPriceOutsource(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<PriceOutsourceListItem>>("/api/price-outsource", undefined, params);
}

export function uploadCsvFile(params: {
  file: File;
  projectId: string;
  periodKey: string;
  importMode: string;
  scopeType: string;
}) {
  const formData = new FormData();
  formData.set("file", params.file);
  formData.set("project_id", params.projectId);
  formData.set("period_key", params.periodKey);
  formData.set("import_mode", params.importMode);
  formData.set("scope_type", params.scopeType);

  return apiFetch<CSVImportResponse>("/api/csv/upload", {
    method: "POST",
    body: formData,
  });
}

export function getImportBatches(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<ImportBatchListItem>>("/api/import-batches", undefined, params);
}

export function generateInvoice(projectId: string, periodKey: string) {
  return apiFetch<InvoiceResponse>("/api/invoices/generate", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, period_key: periodKey }),
  });
}

export function issueInvoice(invoiceId: string) {
  return apiFetch<InvoiceResponse>(`/api/invoices/${invoiceId}/issue`, { method: "POST" });
}

export function generatePayout(projectId: string, workerId: string, periodKey: string) {
  return apiFetch<PayoutResponse>("/api/payouts/generate", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, worker_id: workerId, period_key: periodKey }),
  });
}

export function confirmPayout(payoutId: string) {
  return apiFetch<PayoutResponse>(`/api/payouts/${payoutId}/confirm`, { method: "POST" });
}

export function generateMonthlyBilling(periodKey: string) {
  return apiFetch<MonthlyBillingGenerateResponse>("/api/billing/generate-monthly", {
    method: "POST",
    body: JSON.stringify({ period_key: periodKey }),
  });
}

export function softCloseProject(projectId: string, periodKey: string, reason?: string) {
  return apiFetch<ClosingMutationResponse>("/api/closing/soft", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, period_key: periodKey, reason }),
  });
}

export function hardCloseProject(projectId: string, periodKey: string, approver: string, reason?: string) {
  return apiFetch<ClosingMutationResponse>("/api/closing/hard", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, period_key: periodKey, approver, reason }),
  });
}

export function releaseSoftCloseProject(projectId: string, periodKey: string, approver: string, reason: string) {
  return apiFetch<ClosingMutationResponse>("/api/closing/soft/release", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, period_key: periodKey, approver, reason }),
  });
}

export function releaseHardCloseProject(projectId: string, periodKey: string, approver: string, reason: string) {
  return apiFetch<ClosingMutationResponse>("/api/closing/hard/release", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, period_key: periodKey, approver, reason }),
  });
}