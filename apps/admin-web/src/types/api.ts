export type UserRole = "admin" | "ops" | "accounting" | "site_manager" | "worker";

export interface AuthUser {
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface CSVImportResponse {
  batch_id: string;
  status: string;
  total_rows: number;
  success_rows: number;
  error_rows: number;
  skipped_rows: number;
  superseded_rows: number;
  warnings: string[];
  errors: Array<{
    row: number;
    field: string | null;
    message: string;
  }> | null;
}

export interface ImportBatchListItem {
  id: string;
  file_name: string;
  project_id: string | null;
  project_name: string;
  period_key: string;
  submitted_by: string | null;
  submit_channel: string;
  mode: string;
  scope_type: string | null;
  status: string;
  success_rows: number;
  error_rows: number;
  skipped_rows: number;
  superseded_rows: number;
  has_warnings: boolean;
  errors_preview: Array<{
    row?: number;
    field?: string | null;
    message?: string;
  }>;
  created_at: string;
}

export interface PageResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

export interface DashboardUnprocessedItem {
  item_type: string;
  count: number;
  details: Record<string, unknown>[];
}

export interface DashboardVarianceAlert {
  project_name: string;
  worker_name: string;
  work_date: string;
  planned_minutes: number;
  actual_minutes: number;
  variance_minutes: number;
}

export interface DashboardClosingStatus {
  project_id: string;
  period_key: string;
  project_name: string;
  status: string;
  closed_at: string | null;
  closed_by: string | null;
  release_count: number;
  last_released_at: string | null;
  last_released_by: string | null;
  reclose_deadline: string | null;
}

export interface DashboardResponse {
  unprocessed_items: DashboardUnprocessedItem[];
  variance_alerts: DashboardVarianceAlert[];
  closing_status: DashboardClosingStatus[];
}

export interface MonthlyBillingGenerateResponse {
  period_key: string;
  generated_invoices: number;
  skipped_invoices: number;
  failed_invoices: Array<Record<string, unknown>>;
  generated_payouts: number;
  skipped_payouts: number;
  failed_payouts: Array<Record<string, unknown>>;
}

export interface ClosingMutationResponse {
  id: string;
  project_id: string;
  period_key: string;
  status: string;
  closed_at: string | null;
  closed_by: string | null;
  release_count: number;
  last_released_at: string | null;
  last_released_by: string | null;
  last_release_reason: string | null;
  reclose_deadline: string | null;
}

export interface ActualListItem {
  id: string;
  project_id: string;
  project_name: string;
  worker_id: string;
  worker_name: string;
  role_id: string;
  role_name: string;
  assignment_id: string | null;
  import_batch_id: string;
  import_batch_file_name: string;
  work_date: string;
  start_time: string | null;
  end_time: string | null;
  calc_minutes_billable: number;
  applied_price_sales: string;
  applied_price_outsource: string;
  status: string;
  needs_review: boolean;
  review_reason: string | null;
  external_row_key: string | null;
}

export interface AssignmentListItem {
  id: string;
  shift_slot_id: string;
  project_id: string;
  project_name: string;
  work_date: string;
  shift_label: string | null;
  worker_id: string;
  worker_name: string;
  worker_email: string | null;
  role_id: string;
  role_name: string;
  status: string;
  cancel_reason: string | null;
  worker_response_status: string | null;
  worker_response_requested_at: string | null;
  worker_response_at: string | null;
  worker_response_note: string | null;
  monitoring_status: string | null;
  monitoring_reasons: string[];
  hours_since_response_request: number | null;
  days_until_work: number | null;
  locked_price_sales: string | null;
  locked_price_outsource: string | null;
}

export interface AssignmentReminderSendWorkerResult {
  worker_id: string;
  worker_name: string;
  worker_email: string | null;
  assignment_ids: string[];
  assignment_count: number;
  status: "sent" | "failed" | "skipped_missing_email";
}

export interface AssignmentReminderSendResponse {
  requested_assignment_count: number;
  eligible_assignment_count: number;
  recipient_count: number;
  sent_count: number;
  failed_count: number;
  skipped_missing_email_count: number;
  dry_run: boolean;
  worker_results: AssignmentReminderSendWorkerResult[];
}

export interface AssignmentReminderHistoryItem {
  audit_log_id: string;
  created_at: string;
  actor: string | null;
  actor_role: string | null;
  worker_id: string | null;
  worker_name: string;
  worker_email: string | null;
  status: "sent" | "failed";
  dry_run: boolean;
  assignment_ids: string[];
  assignment_count: number;
}

export interface AssignmentReminderHistoryResponse {
  items: AssignmentReminderHistoryItem[];
}

export interface AssignmentEscalationRecipientResult {
  recipient_email: string;
  recipient_name: string;
  escalated_assignment_count: number;
  status: "sent" | "failed";
}

export interface AssignmentEscalationHistoryItem {
  audit_log_id: string;
  created_at: string;
  actor: string | null;
  actor_role: string | null;
  recipient_name: string;
  recipient_email: string;
  status: "sent" | "failed";
  dry_run: boolean;
  assignment_ids: string[];
  assignment_count: number;
}

export interface AssignmentEscalationHistoryResponse {
  items: AssignmentEscalationHistoryItem[];
}

export interface AssignmentEscalationSendResponse {
  requested_assignment_count: number;
  eligible_assignment_count: number;
  recipient_count: number;
  sent_count: number;
  failed_count: number;
  dry_run: boolean;
  recipient_results: AssignmentEscalationRecipientResult[];
}

export interface AssignmentCancellationHistoryItem {
  audit_log_id: string;
  assignment_id: string;
  project_id: string;
  project_name: string;
  work_date: string;
  shift_label: string | null;
  worker_id: string;
  worker_name: string;
  role_id: string;
  role_name: string;
  canceled_at: string;
  canceled_by: string | null;
  cancel_reason: string | null;
  reopened_at: string | null;
  reopened_by: string | null;
  reopen_reason: string | null;
  current_status: string;
}

export interface AssignmentSelectionSetItem {
  id: string;
  name: string;
  period_key: string;
  assignment_ids: string[];
  total_assignment_count: number;
  available_assignment_count: number;
  is_shared: boolean;
  created_at: string;
  created_by: string | null;
  editable: boolean;
}

export interface AssignmentSelectionSetListResponse {
  items: AssignmentSelectionSetItem[];
}

export interface AssignmentSelectionSetCreateRequest {
  name: string;
  period_key: string;
  assignment_ids: string[];
  is_shared: boolean;
}

export interface AssignmentCreateRequest {
  shift_slot_id: string;
  worker_id: string;
  role_id: string;
  status: "tentative" | "confirmed" | "canceled";
  cancel_reason: string | null;
  locked_price_sales: string | null;
  locked_price_outsource: string | null;
}

export interface AssignmentUpdateRequest {
  shift_slot_id: string;
  worker_id: string;
  role_id: string;
  locked_price_sales: string | null;
  locked_price_outsource: string | null;
}

export interface AssignmentBulkStatusUpdateRequest {
  assignment_ids: string[];
  status: "tentative" | "confirmed" | "canceled";
  cancel_reason: string | null;
  reopen_reason: string | null;
}

export interface AssignmentStatusUpdateRequest {
  status: "tentative" | "confirmed" | "canceled";
  cancel_reason: string | null;
  reopen_reason: string | null;
}

export interface AssignmentBulkMutationResponse {
  updated_count: number;
  assignment_ids: string[];
  status: string;
}

export interface InvoiceListItem {
  id: string;
  invoice_number: string;
  client_id: string;
  client_name: string;
  project_id: string | null;
  project_name: string;
  period_key: string;
  version: number;
  status: string;
  total_amount: string;
  issued_at: string | null;
  has_pdf: boolean;
  pdf_storage_key: string | null;
}

export interface InvoiceResponse {
  id: string;
  invoice_number: string;
  client_name: string;
  project_name: string;
  period_key: string;
  total_amount: string;
  status: string;
  issued_at: string | null;
}

export interface PayoutResponse {
  id: string;
  payout_number: string;
  worker_name: string;
  project_name: string;
  period_key: string;
  total_amount: string;
  status: string;
  approved_at: string | null;
  paid_at: string | null;
}

export interface PayoutListItem {
  id: string;
  payout_number: string;
  payee_name: string;
  payee_type: string;
  project_id: string | null;
  project_name: string;
  period_key: string;
  version: number;
  status: string;
  total_amount: string;
  approved_at: string | null;
  paid_at: string | null;
  has_pdf: boolean;
  pdf_storage_key: string | null;
  default_recipient_email: string | null;
  last_delivery_status: string | null;
  last_delivered_at: string | null;
  last_delivery_recipient: string | null;
}

export interface PayoutDeliveryItem {
  id: string;
  payout_id: string;
  recipient_email: string;
  status: string;
  provider: string | null;
  delivered_by: string | null;
  pdf_storage_key: string | null;
  delivery_note: string | null;
  internal_note: string | null;
  error_message: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface PayoutDeliveryListResponse {
  items: PayoutDeliveryItem[];
}

export interface AuditLogListItem {
  id: string;
  timestamp: string;
  action: string;
  actor: string | null;
  actor_role: string | null;
  project_id: string | null;
  target_type: string | null;
  target_id: string | null;
  reason: string | null;
  details: Record<string, unknown> | null;
  details_summary: string | null;
}

export interface ProjectListItem {
  id: string;
  code: string | null;
  name: string;
  client_id: string | null;
  client_name: string;
  site_id: string | null;
  site_name: string;
  project_type_id: string | null;
  project_type_name: string;
  start_date: string | null;
  end_date: string | null;
  primary_manager_id: string | null;
  secondary_manager_id: string | null;
  notes: string | null;
  is_active: boolean;
}

export interface ProjectCreateRequest {
  name: string;
  code: string | null;
  client_id: string;
  site_id: string | null;
  project_type_id: string | null;
  primary_manager_id: string | null;
  secondary_manager_id: string | null;
  start_date: string | null;
  end_date: string | null;
  notes: string | null;
  is_active: boolean;
}

export interface ProjectUpdateRequest extends ProjectCreateRequest {}

export interface ProjectNotesUpdateRequest {
  notes: string | null;
}

export interface ShiftSlotListItem {
  id: string;
  project_id: string;
  project_name: string;
  work_date: string;
  start_time: string | null;
  end_time: string | null;
  shift_label: string | null;
  required_count: number;
  assigned_count: number;
  notes: string | null;
}

export interface ShiftSlotCreateRequest {
  project_id: string;
  work_date: string;
  start_time: string | null;
  end_time: string | null;
  shift_label: string | null;
  required_count: number;
  notes: string | null;
}

export interface ShiftSlotUpdateRequest extends ShiftSlotCreateRequest {}

export interface ShiftSlotNotesUpdateRequest {
  notes: string | null;
}

export interface ExpenseListItem {
  id: string;
  expense_date: string;
  project_id: string;
  project_name: string;
  worker_id: string | null;
  worker_name: string;
  category: string;
  amount: string;
  status: string;
  approved_by: string | null;
  approved_at: string | null;
  reject_reason: string | null;
  has_receipt: boolean;
}

export interface PriceRuleListItem {
  id: string;
  name: string;
  priority: number;
  conditions: Record<string, unknown>;
  sales_price: string | null;
  outsource_price: string | null;
  valid_from: string | null;
  valid_to: string | null;
  is_active: boolean;
  notes: string | null;
}

export interface PriceRuleCreateRequest {
  name: string;
  priority: number;
  conditions: Record<string, unknown>;
  sales_price: string | null;
  outsource_price: string | null;
  valid_from: string | null;
  valid_to: string | null;
  is_active: boolean;
  notes: string | null;
}

export interface PriceRuleUpdateRequest extends PriceRuleCreateRequest {}

export interface PriceSalesListItem {
  id: string;
  project_id: string | null;
  project_name: string;
  role_id: string | null;
  role_name: string;
  client_id: string | null;
  client_name: string;
  unit_price: string;
  unit_type: string;
  valid_from: string | null;
  valid_to: string | null;
  is_default: boolean;
  notes: string | null;
}

export interface PriceSalesCreateRequest {
  project_id: string | null;
  role_id: string | null;
  client_id: string | null;
  unit_price: string;
  unit_type: "hourly" | "daily" | "monthly" | "fixed";
  valid_from: string | null;
  valid_to: string | null;
  is_default: boolean;
  notes: string | null;
}

export interface PriceSalesUpdateRequest extends PriceSalesCreateRequest {}

export interface PriceOutsourceListItem {
  id: string;
  project_id: string | null;
  project_name: string;
  worker_id: string | null;
  worker_name: string;
  role_id: string | null;
  role_name: string;
  unit_price: string;
  unit_type: string;
  valid_from: string | null;
  valid_to: string | null;
  is_default: boolean;
  notes: string | null;
}

export interface PriceOutsourceCreateRequest {
  project_id: string | null;
  worker_id: string | null;
  role_id: string | null;
  unit_price: string;
  unit_type: "hourly" | "daily" | "monthly" | "fixed";
  valid_from: string | null;
  valid_to: string | null;
  is_default: boolean;
  notes: string | null;
}

export interface PriceOutsourceUpdateRequest extends PriceOutsourceCreateRequest {}

export interface WorkerListItem {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  is_active: boolean;
  introducer_supplier_id: string | null;
  introducer_supplier_name: string | null;
  notes: string | null;
}

export interface WorkerCreateRequest {
  name: string;
  email: string | null;
  phone: string | null;
  introducer_supplier_id: string | null;
  notes: string | null;
  is_active: boolean;
}

export interface WorkerUpdateRequest extends WorkerCreateRequest {}

export interface WorkerAvailabilityPreference {
  worker_id: string;
  weekly_default_statuses: Record<string, string>;
  holiday_default_status: string | null;
  auto_apply_enabled: boolean;
  updated_at: string | null;
}

export interface SupplierListItem {
  id: string;
  name: string;
  contact_email: string | null;
  contact_phone: string | null;
  payout_terms_days: number;
  default_daily_price: string | null;
  is_active: boolean;
  notes: string | null;
}

export interface SupplierCreateRequest {
  name: string;
  contact_email: string | null;
  contact_phone: string | null;
  payout_terms_days: number;
  default_daily_price: string | null;
  is_active: boolean;
  notes: string | null;
}

export interface SupplierUpdateRequest extends SupplierCreateRequest {}

export interface ClientListItem {
  id: string;
  name: string;
  code: string | null;
  contact_name: string | null;
  contact_email: string | null;
}

export interface ClientCreateRequest {
  name: string;
  code: string | null;
  address: string | null;
  contact_name: string | null;
  contact_email: string | null;
}

export interface SiteListItem {
  id: string;
  name: string;
  code: string | null;
  address: string | null;
}

export interface SiteCreateRequest {
  name: string;
  code: string | null;
  address: string | null;
}

export interface ProjectTypeListItem {
  id: string;
  name: string;
  code: string | null;
  description: string | null;
}

export interface ProjectTypeCreateRequest {
  name: string;
  code: string | null;
  description: string | null;
}

export interface RoleListItem {
  id: string;
  name: string;
  code: string | null;
  description: string | null;
}

export interface RoleCreateRequest {
  name: string;
  code: string | null;
  description: string | null;
}
