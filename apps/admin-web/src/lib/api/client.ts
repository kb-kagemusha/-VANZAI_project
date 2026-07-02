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
  ProjectTypeTreeResponse,
  PublicIntroducerIdentityRegistrationSubmitRequest,
  PublicRegistrationAccessResponse,
  PublicRegistrationFileUploadResponse,
  PublicRegistrationSubmitResponse,
  PublicSupplierCorporationRegistrationSubmitRequest,
  PublicSupplierIndividualRegistrationSubmitRequest,
  PublicWorkerRegistrationSubmitRequest,
  RegistrationLinkCreateRequest,
  RegistrationLinkResponse,
  RegistrationRequestApproveRequest,
  RegistrationRequestDetailResponse,
  RegistrationRequestListItem,
  RegistrationRequestRejectRequest,
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
  WorkerQualsUpdateRequest,
  NoticeCreateRequest,
  NoticeListItem,
  NoticeListResponse,
  AvailabilityCalendarResponse,
  VanzaiStaffItem,
  VanzaiStaffCreateRequest,
  VanzaiStaffUpdateRequest,
  ClientStaffItem,
  ClientStaffCreateRequest,
  ClientStaffUpdateRequest,
  WorkerBankAccountItem,
  WorkerBankAccountListResponse,
  WorkerBankAccountCreateRequest,
  WorkerBankAccountUpdateRequest,
  SupplierBankAccountItem,
  SupplierBankAccountListResponse,
  SupplierBankAccountCreateRequest,
  SupplierBankAccountUpdateRequest,
  OcrSourceImageItem,
  OcrSourceImageListResponse,
  OcrParseJobResponse,
  OcrExtractedRowItem,
  OcrExtractedRowListResponse,
  OcrMonthlySummaryResponse,
  OcrReconciliationBatchResponse,
  OcrSelfReportCompareResponse,
  OcrSourceType,
  InventorySnapshotItem,
  InventorySnapshotListResponse,
  InventorySnapshotCreateRequest,
  InventorySnapshotUpdateRequest,
  InventoryReconciliationBatchResponse,
  InventoryReconciliationResultItem,
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

async function publicApiFetch<T>(
  path: string,
  init?: RequestInit,
  params?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  const headers = new Headers(init?.headers);

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
    throw new ApiError(response.status, message || "API request failed", payload);
  }

  return payload as T;
}

async function downloadBinaryFileWithQuery(path: string, fallbackFileName: string, params?: Record<string, string | number | boolean | undefined>) {
  const headers = new Headers();
  const token = getStoredAccessToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(buildUrl(path, params), { headers });

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

  let response: Response;
  try {
    response = await fetch(buildUrl("/api/auth/token"), {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: form.toString(),
    });
  } catch {
    throw new ApiError(
      0,
      "認証サーバーに接続できません。APIが停止している可能性があります。しばらく待ってから再試行してください。",
    );
  }
  const payload = await readResponse(response);

  if (!response.ok) {
    const message =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? String(payload.detail)
        : response.status === 401
          ? "ユーザー名またはパスワードが正しくありません"
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

export function updateProfile(data: { display_name: string }): Promise<AuthUser> {
  return apiFetch<AuthUser>("/api/auth/profile", {
    method: "PUT",
    body: JSON.stringify(data),
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

export function generateInvoice(params: {
  projectId: string;
  periodKey: string;
  documentType?: "invoice" | "estimate";
  clientStaffId?: string | null;
  subject?: string | null;
  fixedOfficeFeeAmount?: string | null;
  billingDate?: string | null;
}) {
  return apiFetch<InvoiceResponse>("/api/invoices/generate", {
    method: "POST",
    body: JSON.stringify({
      project_id: params.projectId,
      period_key: params.periodKey,
      document_type: params.documentType || "invoice",
      client_staff_id: params.clientStaffId || null,
      subject: params.subject || null,
      fixed_office_fee_amount: params.fixedOfficeFeeAmount || null,
      billing_date: params.billingDate || null,
    }),
  });
}

export function issueInvoice(invoiceId: string) {
  return apiFetch<InvoiceResponse>(`/api/invoices/${invoiceId}/issue`, { method: "POST" });
}

export function downloadInvoicePdf(invoiceId: string) {
  return downloadBinaryFile(`/api/invoices/${invoiceId}/pdf`, `invoice_${invoiceId}.pdf`);
}

export function generatePayout(params: {
  projectId: string;
  recipientType: string;
  recipientId: string;
  supportFeeAmount?: string;
  periodKey: string;
}) {
  return apiFetch<PayoutResponse>("/api/payouts/generate", {
    method: "POST",
    body: JSON.stringify({
      project_id: params.projectId,
      recipient_type: params.recipientType,
      recipient_id: params.recipientId,
      worker_id: params.recipientType === "worker" ? params.recipientId : null,
      support_fee_amount: params.supportFeeAmount || null,
      period_key: params.periodKey,
    }),
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

export function patchWorkerQuals(workerId: string, body: WorkerQualsUpdateRequest) {
  return apiFetch<WorkerListItem>(`/api/workers/${workerId}/quals`, {
    method: "PATCH",
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

export function getProjectTypeTree(params?: Record<string, string | number | boolean | undefined>) {
  return apiFetch<ProjectTypeTreeResponse>("/api/project-types/tree", undefined, params);
}

export function getRegistrationRequests(params?: Record<string, string | number | boolean | undefined>) {
  return apiFetch<PageResponse<RegistrationRequestListItem>>("/api/registration-requests", undefined, params);
}

export function getRegistrationRequest(requestId: string) {
  return apiFetch<RegistrationRequestDetailResponse>(`/api/registration-requests/${requestId}`);
}

export function approveRegistrationRequest(requestId: string, body: RegistrationRequestApproveRequest) {
  return apiFetch<RegistrationRequestDetailResponse>(`/api/registration-requests/${requestId}/approve`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function rejectRegistrationRequest(requestId: string, body: RegistrationRequestRejectRequest) {
  return apiFetch<RegistrationRequestDetailResponse>(`/api/registration-requests/${requestId}/reject`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function createRegistrationLink(body: RegistrationLinkCreateRequest) {
  return apiFetch<RegistrationLinkResponse>("/api/registration-links", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function resetRegistrationLinkPinLock(requestId: string) {
  return apiFetch<RegistrationRequestDetailResponse>(`/api/registration-links/${requestId}/reset-pin-lock`, {
    method: "POST",
  });
}

export function reissueRegistrationLink(requestId: string, body: RegistrationLinkCreateRequest) {
  return apiFetch<RegistrationLinkResponse>(`/api/registration-links/${requestId}/reissue`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function downloadRegistrationRequestFile(requestId: string, fileId: string, reason: string) {
  return downloadBinaryFileWithQuery(`/api/registration-requests/${requestId}/files/${fileId}`, `registration_file_${fileId}`, { reason });
}

export function getPublicRegistrationAccess(formType: string, token: string, pin: string) {
  return publicApiFetch<PublicRegistrationAccessResponse>(`/public/registrations/${formType}`, undefined, { token, pin });
}

export function uploadPublicRegistrationFile(params: {
  formType: string;
  token: string;
  pin: string;
  documentType: string;
  documentPart: string;
  file: File;
}) {
  const formData = new FormData();
  formData.set("token", params.token);
  formData.set("pin", params.pin);
  formData.set("document_type", params.documentType);
  formData.set("document_part", params.documentPart);
  formData.set("file", params.file);
  return publicApiFetch<PublicRegistrationFileUploadResponse>(`/public/registrations/${params.formType}/files`, {
    method: "POST",
    body: formData,
  });
}

export function submitPublicWorkerRegistration(body: PublicWorkerRegistrationSubmitRequest) {
  return publicApiFetch<PublicRegistrationSubmitResponse>("/public/registrations/worker", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function submitPublicSupplierIndividualRegistration(body: PublicSupplierIndividualRegistrationSubmitRequest) {
  return publicApiFetch<PublicRegistrationSubmitResponse>("/public/registrations/supplier-individual", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function submitPublicSupplierCorporationRegistration(body: PublicSupplierCorporationRegistrationSubmitRequest) {
  return publicApiFetch<PublicRegistrationSubmitResponse>("/public/registrations/supplier-corporation", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function submitPublicIntroducerIdentityRegistration(body: PublicIntroducerIdentityRegistrationSubmitRequest) {
  return publicApiFetch<PublicRegistrationSubmitResponse>("/public/registrations/introducer-identity", {
    method: "POST",
    body: JSON.stringify(body),
  });
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

export function createRole(body: { name: string; code: string | null; description: string | null }) {
  return apiFetch<RoleListItem>("/api/roles", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ===========================
// Staff Notices
// ===========================

export function createNotice(body: NoticeCreateRequest) {
  return apiFetch<NoticeListItem>("/api/notices", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listNotices(params?: {
  notice_type?: string;
  target_type?: string;
  offset?: number;
  limit?: number;
}) {
  return apiFetch<NoticeListResponse>("/api/notices", undefined, params as Record<string, string | number | boolean | undefined>);
}

export function deleteNotice(noticeId: string) {
  return apiFetch<void>(`/api/notices/${noticeId}`, { method: "DELETE" });
}

// ===========================
// VanzaiStaff
// ===========================

export function getVanzaiStaff(params?: Record<string, string | number | boolean | undefined>) {
  return apiFetch<{ items: VanzaiStaffItem[]; total: number; page: number; limit: number }>("/api/vanzai-staff", undefined, params);
}

export function createVanzaiStaff(body: VanzaiStaffCreateRequest) {
  return apiFetch<VanzaiStaffItem>("/api/vanzai-staff", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateVanzaiStaff(staffId: string, body: VanzaiStaffUpdateRequest) {
  return apiFetch<VanzaiStaffItem>(`/api/vanzai-staff/${staffId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

// ===========================
// ClientStaff
// ===========================

export function getClientStaff(clientId: string, params?: Record<string, string | number | boolean | undefined>) {
  return apiFetch<{ items: ClientStaffItem[]; total: number; page: number; limit: number }>(`/api/clients/${clientId}/staff`, undefined, params);
}

export function createClientStaff(clientId: string, body: ClientStaffCreateRequest) {
  return apiFetch<ClientStaffItem>(`/api/clients/${clientId}/staff`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateClientStaff(clientId: string, staffMemberId: string, body: ClientStaffUpdateRequest) {
  return apiFetch<ClientStaffItem>(`/api/clients/${clientId}/staff/${staffMemberId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

// ===========================
// WorkerBankAccount
// ===========================

export function getWorkerBankAccounts(workerId: string) {
  return apiFetch<WorkerBankAccountListResponse>(`/api/workers/${workerId}/bank-accounts`);
}

export function createWorkerBankAccount(workerId: string, body: WorkerBankAccountCreateRequest) {
  return apiFetch<WorkerBankAccountItem>(`/api/workers/${workerId}/bank-accounts`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateWorkerBankAccount(workerId: string, accountId: string, body: WorkerBankAccountUpdateRequest) {
  return apiFetch<WorkerBankAccountItem>(`/api/workers/${workerId}/bank-accounts/${accountId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

// ===========================
// SupplierBankAccount
// ===========================

export function getSupplierBankAccounts(supplierId: string) {
  return apiFetch<SupplierBankAccountListResponse>(`/api/suppliers/${supplierId}/bank-accounts`);
}

export function createSupplierBankAccount(supplierId: string, body: SupplierBankAccountCreateRequest) {
  return apiFetch<SupplierBankAccountItem>(`/api/suppliers/${supplierId}/bank-accounts`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateSupplierBankAccount(supplierId: string, accountId: string, body: SupplierBankAccountUpdateRequest) {
  return apiFetch<SupplierBankAccountItem>(`/api/suppliers/${supplierId}/bank-accounts/${accountId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

// ===========================
// OCR Receipt
// ===========================

export function uploadOcrImage(file: File, sourceType: OcrSourceType) {
  const formData = new FormData();
  formData.set("file", file);
  formData.set("source_type", sourceType);
  return apiFetch<OcrSourceImageItem>("/api/ocr/images", {
    method: "POST",
    body: formData,
  });
}

export function listOcrImages(params?: Record<string, string | number | boolean | undefined>) {
  return apiFetch<OcrSourceImageListResponse>("/api/ocr/images", undefined, params);
}

export async function fetchOcrImageBlobUrl(imageId: string): Promise<string> {
  const headers = new Headers();
  const token = getStoredAccessToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(buildUrl(`/api/ocr/images/${imageId}/file`), { headers });
  if (!response.ok) {
    const payload = await readResponse(response);
    const message =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? String(payload.detail)
        : response.statusText;
    if (response.status === 401) {
      emitUnauthorized();
    }
    throw new ApiError(response.status, message || "Image fetch failed", payload);
  }

  const blob = await response.blob();
  return window.URL.createObjectURL(blob);
}

export function deleteOcrImages(imageIds: string[]) {
  return apiFetch<{ deleted_count: number }>("/api/ocr/images", {
    method: "DELETE",
    body: JSON.stringify({ image_ids: imageIds }),
  });
}

export function renameOcrImage(imageId: string, originalFilename: string) {
  return apiFetch<OcrSourceImageItem>(`/api/ocr/images/${imageId}`, {
    method: "PATCH",
    body: JSON.stringify({ original_filename: originalFilename }),
  });
}

export function parseOcrImages(imageIds: string[]) {
  return apiFetch<OcrParseJobResponse>("/api/ocr/jobs/parse", {
    method: "POST",
    body: JSON.stringify({ image_ids: imageIds }),
  });
}

export function listOcrRows(params?: Record<string, string | number | boolean | undefined>) {
  return apiFetch<OcrExtractedRowListResponse>("/api/ocr/rows", undefined, params);
}

export function updateOcrRow(rowId: string, body: Partial<OcrExtractedRowItem>) {
  return apiFetch<OcrExtractedRowItem>(`/api/ocr/rows/${rowId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function confirmOcrRows(rowIds: string[]) {
  return apiFetch<{ confirmed_count: number }>("/api/ocr/rows/confirm", {
    method: "POST",
    body: JSON.stringify({ row_ids: rowIds }),
  });
}

export function deleteOcrRows(rowIds: string[]) {
  return apiFetch<{ deleted_count: number }>("/api/ocr/rows", {
    method: "DELETE",
    body: JSON.stringify({ row_ids: rowIds }),
  });
}

export function getOcrMonthlySummary() {
  return apiFetch<OcrMonthlySummaryResponse>("/api/ocr/monthly-summary");
}

export function downloadOcrCsv(periodKey: string, sourceType?: string) {
  return downloadBinaryFileWithQuery(
    `/api/ocr/exports/${periodKey}.csv`,
    `ocr_${periodKey}.csv`,
    sourceType ? { source_type: sourceType } : undefined,
  );
}

export function downloadAllOcrCsv(sourceType?: string) {
  return downloadBinaryFileWithQuery(
    "/api/ocr/exports/all.csv",
    "ocr_all.csv",
    sourceType ? { source_type: sourceType } : undefined,
  );
}

export function runOcrReconciliation(params: {
  file: File;
  columnMapping: Record<string, string>;
  periodKey?: string;
}) {
  const formData = new FormData();
  formData.set("file", params.file);
  formData.set("column_mapping", JSON.stringify(params.columnMapping));
  if (params.periodKey) {
    formData.set("period_key", params.periodKey);
  }
  return apiFetch<OcrReconciliationBatchResponse>("/api/ocr/reconciliation", {
    method: "POST",
    body: formData,
  });
}

export function compareOcrSelfReport(periodKey: string, projectId?: string) {
  return apiFetch<OcrSelfReportCompareResponse>("/api/ocr/compare/self-report", undefined, {
    period_key: periodKey,
    project_id: projectId,
  });
}

export function linkOcrRow(
  rowId: string,
  body: { linked_entity_type: string; linked_entity_id: string; project_id?: string },
) {
  return apiFetch<OcrExtractedRowItem>(`/api/ocr/rows/${rowId}/link`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function voidOcrRow(rowId: string, voidReason: string) {
  return apiFetch<OcrExtractedRowItem>(`/api/ocr/rows/${rowId}/void`, {
    method: "POST",
    body: JSON.stringify({ void_reason: voidReason }),
  });
}

export function setOcrRowReconciliationEligibility(
  rowId: string,
  eligible: boolean,
  excludedReason?: string | null,
) {
  return apiFetch<OcrExtractedRowItem>(`/api/ocr/rows/${rowId}/reconciliation-eligibility`, {
    method: "POST",
    body: JSON.stringify({ eligible, excluded_reason: excludedReason ?? null }),
  });
}

export function downloadSettlementCsv(periodKey?: string) {
  return downloadBinaryFileWithQuery(
    "/api/ocr/exports/settlement.csv",
    `ocr_settlement_${periodKey || "all"}.csv`,
    periodKey ? { period_key: periodKey } : undefined,
  );
}

// ===========================
// Inventory Reconciliation (計画書 v4 Phase 2)
// ===========================

export function listInventorySnapshots(params?: {
  branch_id?: string;
  terminal_short_id?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}) {
  return apiFetch<InventorySnapshotListResponse>("/api/inventory/snapshots", undefined, params);
}

export function createInventorySnapshot(body: InventorySnapshotCreateRequest) {
  return apiFetch<InventorySnapshotItem>("/api/inventory/snapshots", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateInventorySnapshot(snapshotId: string, body: InventorySnapshotUpdateRequest) {
  return apiFetch<InventorySnapshotItem>(`/api/inventory/snapshots/${snapshotId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteInventorySnapshot(snapshotId: string) {
  return apiFetch<{ deleted: boolean }>(`/api/inventory/snapshots/${snapshotId}`, {
    method: "DELETE",
  });
}

export function runInventoryReconciliation(body: { date_from?: string; date_to?: string; period_key?: string }) {
  return apiFetch<InventoryReconciliationBatchResponse>("/api/inventory/reconciliation/run", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getInventoryReconciliationBatch(batchId: string) {
  return apiFetch<InventoryReconciliationBatchResponse>(`/api/inventory/reconciliation/batches/${batchId}`);
}

export function updateInventoryReconciliationResult(
  resultId: string,
  body: { diff_reason_category?: string | null; notes?: string | null; match_status?: string },
) {
  return apiFetch<InventoryReconciliationResultItem>(`/api/inventory/reconciliation/results/${resultId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}