import type {
  ActualListItem,
  AssignmentCancellationHistoryItem,
  AssignmentBulkMutationResponse,
  AssignmentEscalationHistoryResponse,
  AssignmentEscalationSendResponse,
  AssignmentReminderHistoryResponse,
  AssignmentReminderSendResponse,
  AssignmentSelectionSetCreateRequest,
  AssignmentSelectionSetItem,
  AssignmentSelectionSetListResponse,
  AssignmentBulkStatusUpdateRequest,
  AssignmentCreateRequest,
  AssignmentUpdateRequest,
  AuditLogListItem,
  AssignmentListItem,
  AssignmentStatusUpdateRequest,
  CSVImportResponse,
  ClientCreateRequest,
  ClientListItem,
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
  PayoutDeliveryItem,
  PayoutDeliveryListResponse,
  PayoutResponse,
  PriceOutsourceCreateRequest,
  PriceOutsourceListItem,
  PriceOutsourceUpdateRequest,
  PriceRuleCreateRequest,
  PriceRuleListItem,
  PriceRuleUpdateRequest,
  PriceSalesCreateRequest,
  PriceSalesListItem,
  PriceSalesUpdateRequest,
  ProjectCreateRequest,
  ProjectListItem,
  ProjectUpdateRequest,
  ProjectNotesUpdateRequest,
  ProjectTypeCreateRequest,
  ProjectTypeListItem,
  RoleCreateRequest,
  RoleListItem,
  ShiftSlotCreateRequest,
  ShiftSlotListItem,
  ShiftSlotUpdateRequest,
  ShiftSlotNotesUpdateRequest,
  SiteCreateRequest,
  SiteListItem,
  SupplierListItem,
  SupplierCreateRequest,
  SupplierUpdateRequest,
  TokenResponse,
  WorkerAvailabilityPreference,
  WorkerListItem,
  WorkerCreateRequest,
  WorkerUpdateRequest,
  AvailabilityCalendarResponse,
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

  return API_BASE_URL ? url.toString() : `${path}${url.search}`;
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

async function downloadBinaryFile(path: string, fallbackFileName: string) {
  const headers = new Headers();
  const token = getStoredAccessToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(buildUrl(path), { headers });

  if (!response.ok) {
    const payload = await readResponse(response);
    const message =
      typeof payload === "object" && payload !== null && "message" in payload
        ? String(payload.message)
        : typeof payload === "object" && payload !== null && "detail" in payload
          ? String(payload.detail)
          : response.statusText;

    if (response.status === 401) {
      emitUnauthorized();
    }

    throw new ApiError(response.status, message || "ファイルのダウンロードに失敗しました", payload);
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

export function getDashboard(periodKey: string): Promise<DashboardResponse> {
  return apiFetch<DashboardResponse>("/api/dashboard", undefined, { period_key: periodKey });
}

export function getActuals(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<ActualListItem>>("/api/actuals", undefined, params);
}

export function getAssignments(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<AssignmentListItem>>("/api/assignments", undefined, params);
}

export function getAssignmentCancellationHistory(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<AssignmentCancellationHistoryItem>>("/api/assignments/cancellation-history", undefined, params);
}

export function getAssignmentSelectionSets(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<AssignmentSelectionSetListResponse>("/api/assignments/selection-sets", undefined, params);
}

export function createAssignmentSelectionSet(body: AssignmentSelectionSetCreateRequest) {
  return apiFetch<AssignmentSelectionSetItem>("/api/assignments/selection-sets", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteAssignmentSelectionSet(selectionSetId: string) {
  return apiFetch<null>(`/api/assignments/selection-sets/${selectionSetId}`, {
    method: "DELETE",
  });
}

export function createAssignment(body: AssignmentCreateRequest) {
  return apiFetch<AssignmentListItem>("/api/assignments", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateAssignment(assignmentId: string, body: AssignmentUpdateRequest) {
  return apiFetch<AssignmentListItem>(`/api/assignments/${assignmentId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function bulkUpdateAssignmentStatus(body: AssignmentBulkStatusUpdateRequest) {
  return apiFetch<AssignmentBulkMutationResponse>("/api/assignments/status/bulk", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateAssignmentStatus(assignmentId: string, body: AssignmentStatusUpdateRequest) {
  return apiFetch<AssignmentListItem>(`/api/assignments/${assignmentId}/status`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function sendAssignmentReminders(body: { assignment_ids: string[]; dry_run?: boolean }) {
  return apiFetch<AssignmentReminderSendResponse>("/api/assignments/reminders/send", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getAssignmentReminderHistory(body: { assignment_ids: string[]; limit?: number }) {
  return apiFetch<AssignmentReminderHistoryResponse>("/api/assignments/reminders/history", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function sendAssignmentEscalations(body: { assignment_ids: string[]; dry_run?: boolean }) {
  return apiFetch<AssignmentEscalationSendResponse>("/api/assignments/reminders/escalate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getAssignmentEscalationHistory(body: { assignment_ids: string[]; limit?: number }) {
  return apiFetch<AssignmentEscalationHistoryResponse>("/api/assignments/reminders/escalations/history", {
    method: "POST",
    body: JSON.stringify(body),
  });
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

export function createProject(body: ProjectCreateRequest) {
  return apiFetch<ProjectListItem>("/api/projects", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateProject(projectId: string, body: ProjectUpdateRequest) {
  return apiFetch<ProjectListItem>(`/api/projects/${projectId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function updateProjectNotes(projectId: string, body: ProjectNotesUpdateRequest) {
  return apiFetch<ProjectListItem>(`/api/projects/${projectId}/notes`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function getShiftSlots(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<ShiftSlotListItem>>("/api/shift-slots", undefined, params);
}

export function createShiftSlot(body: ShiftSlotCreateRequest) {
  return apiFetch<ShiftSlotListItem>("/api/shift-slots", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateShiftSlot(shiftSlotId: string, body: ShiftSlotUpdateRequest) {
  return apiFetch<ShiftSlotListItem>(`/api/shift-slots/${shiftSlotId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function updateShiftSlotNotes(shiftSlotId: string, body: ShiftSlotNotesUpdateRequest) {
  return apiFetch<ShiftSlotListItem>(`/api/shift-slots/${shiftSlotId}/notes`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function getExpenses(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<ExpenseListItem>>("/api/expenses", undefined, params);
}

export function approveExpense(expenseId: string) {
  return apiFetch<ExpenseListItem>(`/api/expenses/${expenseId}/approve`, {
    method: "POST",
  });
}

export function rejectExpense(expenseId: string, rejectReason: string) {
  return apiFetch<ExpenseListItem>(`/api/expenses/${expenseId}/reject`, {
    method: "POST",
    body: JSON.stringify({ reject_reason: rejectReason }),
  });
}

export function downloadExpenseReceipt(expenseId: string) {
  return downloadBinaryFile(`/api/expenses/${expenseId}/receipt`, `expense_receipt_${expenseId}`);
}

export function getPriceRules(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<PriceRuleListItem>>("/api/price-rules", undefined, params);
}

export function createPriceRule(body: PriceRuleCreateRequest) {
  return apiFetch<PriceRuleListItem>("/api/price-rules", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updatePriceRule(priceRuleId: string, body: PriceRuleUpdateRequest) {
  return apiFetch<PriceRuleListItem>(`/api/price-rules/${priceRuleId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function getPriceSales(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<PriceSalesListItem>>("/api/price-sales", undefined, params);
}

export function createPriceSales(body: PriceSalesCreateRequest) {
  return apiFetch<PriceSalesListItem>("/api/price-sales", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updatePriceSales(priceSalesId: string, body: PriceSalesUpdateRequest) {
  return apiFetch<PriceSalesListItem>(`/api/price-sales/${priceSalesId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function getPriceOutsource(params: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<PriceOutsourceListItem>>("/api/price-outsource", undefined, params);
}

export function createPriceOutsource(body: PriceOutsourceCreateRequest) {
  return apiFetch<PriceOutsourceListItem>("/api/price-outsource", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updatePriceOutsource(priceOutsourceId: string, body: PriceOutsourceUpdateRequest) {
  return apiFetch<PriceOutsourceListItem>(`/api/price-outsource/${priceOutsourceId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
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

export function downloadInvoicePdf(invoiceId: string) {
  return downloadBinaryFile(`/api/invoices/${invoiceId}/pdf`, `invoice_${invoiceId}.pdf`);
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

export function markPayoutPaid(payoutId: string) {
  return apiFetch<PayoutResponse>(`/api/payouts/${payoutId}/paid`, { method: "POST" });
}

export function downloadPayoutPdf(payoutId: string) {
  return downloadBinaryFile(`/api/payouts/${payoutId}/pdf`, `payout_${payoutId}.pdf`);
}

export function deliverPayout(
  payoutId: string,
  options?: {
    recipientEmail?: string;
    deliveryNote?: string;
    internalNote?: string;
  },
) {
  return apiFetch<PayoutDeliveryItem>(`/api/payouts/${payoutId}/deliver`, {
    method: "POST",
    body: JSON.stringify({
      recipient_email: options?.recipientEmail || null,
      delivery_note: options?.deliveryNote || null,
      internal_note: options?.internalNote || null,
    }),
  });
}

export function getPayoutDeliveries(payoutId: string) {
  return apiFetch<PayoutDeliveryListResponse>(`/api/payouts/${payoutId}/deliveries`);
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

// ===========================
// Master Data
// ===========================

export function getWorkers(params?: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<WorkerListItem>>("/api/workers", undefined, params);
}

export function createWorker(body: WorkerCreateRequest) {
  return apiFetch<WorkerListItem>("/api/workers", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateWorker(workerId: string, body: WorkerUpdateRequest) {
  return apiFetch<WorkerListItem>(`/api/workers/${workerId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function deleteWorker(workerId: string) {
  return apiFetch<void>(`/api/workers/${workerId}`, { method: "DELETE" });
}

export function getWorkerAvailabilityPreferences(workerId: string) {
  return apiFetch<WorkerAvailabilityPreference>(`/api/workers/${workerId}/availability-preferences`);
}

export function getAvailabilityCalendar(params: {
  date_from: string;
  date_to: string;
  is_active?: boolean;
}) {
  return apiFetch<AvailabilityCalendarResponse>("/api/availability-calendar", undefined, params as Record<string, string | number | boolean | undefined>);
}

export function getSuppliers(params?: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<SupplierListItem>>("/api/suppliers", undefined, params);
}

export function createSupplier(body: SupplierCreateRequest) {
  return apiFetch<SupplierListItem>("/api/suppliers", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateSupplier(supplierId: string, body: SupplierUpdateRequest) {
  return apiFetch<SupplierListItem>(`/api/suppliers/${supplierId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function getClients(params?: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<ClientListItem>>("/api/clients", undefined, params);
}

export function createClient(body: ClientCreateRequest) {
  return apiFetch<ClientListItem>("/api/clients", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getSites(params?: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<SiteListItem>>("/api/sites", undefined, params);
}

export function createSite(body: SiteCreateRequest) {
  return apiFetch<SiteListItem>("/api/sites", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getProjectTypes(params?: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<ProjectTypeListItem>>("/api/project-types", undefined, params);
}

export function createProjectType(body: ProjectTypeCreateRequest) {
  return apiFetch<ProjectTypeListItem>("/api/project-types", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getRoles(params?: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<RoleListItem>>("/api/roles", undefined, params);
}

export function createRole(body: RoleCreateRequest) {
  return apiFetch<RoleListItem>("/api/roles", {
    method: "POST",
    body: JSON.stringify(body),
  });
}