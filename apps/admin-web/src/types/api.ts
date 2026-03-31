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
  role_id: string;
  role_name: string;
  status: string;
  cancel_reason: string | null;
  locked_price_sales: string | null;
  locked_price_outsource: string | null;
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
  client_name: string;
  site_name: string;
  project_type_name: string;
  start_date: string | null;
  end_date: string | null;
  is_active: boolean;
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
  has_receipt: boolean;
}

export interface PriceRuleListItem {
  id: string;
  name: string;
  priority: number;
  sales_price: string | null;
  outsource_price: string | null;
  valid_from: string | null;
  valid_to: string | null;
  is_active: boolean;
}

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
}

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
}