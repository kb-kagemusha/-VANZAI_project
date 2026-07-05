export type UserRole = "admin" | "ops" | "accounting" | "site_manager" | "worker";

export interface AuthUser {
  username: string;
  display_name: string | null;
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
  billing_date: string;
  document_type: string;
  subject: string | null;
  addressee_company_name: string | null;
  addressee_name: string | null;
  fixed_office_fee_amount: string | null;
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
  document_type: string;
  client_name: string;
  project_name: string;
  period_key: string;
  billing_date: string;
  subject: string | null;
  addressee_company_name: string | null;
  addressee_name: string | null;
  addressee_email: string | null;
  addressee_address: string | null;
  fixed_office_fee_amount: string | null;
  total_amount: string;
  status: string;
  lines: Array<{
    line_type: string;
    description: string;
    quantity: string | null;
    unit_price: string | null;
    amount: string;
  }>;
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
  recipient_type: string | null;
  recipient_id: string | null;
  payee_name_snapshot: string | null;
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
  vanzai_manager_id: string | null;
  vanzai_manager_name: string | null;
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
  vanzai_manager_id: string | null;
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
  furigana: string | null;
  email: string | null;
  phone: string | null;
  sole_proprietor_name: string | null;
  emergency_contact_name_kana: string | null;
  emergency_contact_phone: string | null;
  gender: string | null;
  invoice_registration_status: string | null;
  invoice_number: string | null;
  is_active: boolean;
  introducer_supplier_id: string | null;
  introducer_supplier_name: string | null;
  notes: string | null;
  smoking_area_ok: boolean | null;
  has_p_shirt: boolean | null;
  has_best: boolean | null;
  stores_training_done: boolean | null;
  pioneer_training_done: boolean | null;
  p_shirt_count: number | null;
  license_type: string | null;
}

export interface WorkerCreateRequest {
  name: string;
  furigana: string | null;
  email: string | null;
  phone: string | null;
  sole_proprietor_name: string | null;
  emergency_contact_name_kana: string | null;
  emergency_contact_phone: string | null;
  gender: string | null;
  invoice_registration_status: string | null;
  invoice_number: string | null;
  introducer_supplier_id: string | null;
  notes: string | null;
  is_active: boolean;
  smoking_area_ok: boolean | null;
  has_p_shirt: boolean | null;
  has_best: boolean | null;
  stores_training_done: boolean | null;
  pioneer_training_done: boolean | null;
  p_shirt_count: number | null;
  license_type: string | null;
}

export interface WorkerUpdateRequest extends WorkerCreateRequest {}

export interface WorkerQualsUpdateRequest {
  smoking_area_ok: boolean | null;
  p_shirt_count: number | null;
  has_best: boolean | null;
  stores_training_done: boolean | null;
  pioneer_training_done: boolean | null;
  license_type: string | null;
}

export interface CalendarDayAssignment {
  id: string;
  project_id: string;
  project_name: string;
  shift_slot_id: string;
  shift_label: string | null;
  status: string;
  role_name: string;
}

export interface CalendarDayInfo {
  availability_status: string | null;
  availability_notes: string | null;
  assignments: CalendarDayAssignment[];
}

export interface CalendarWorkerRow {
  id: string;
  name: string;
  is_active: boolean;
  smoking_area_ok: boolean | null;
  has_p_shirt: boolean | null;
  has_best: boolean | null;
  stores_training_done: boolean | null;
  pioneer_training_done: boolean | null;
  p_shirt_count: number | null;
  license_type: string | null;
  days: Record<string, CalendarDayInfo>;
}

export interface AvailabilityCalendarResponse {
  date_from: string;
  date_to: string;
  workers: CalendarWorkerRow[];
}

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
  supplier_type: string | null;
  entity_type: string | null;
  payout_terms_days: number;
  default_daily_price: string | null;
  is_active: boolean;
  notes: string | null;
}

export interface SupplierCreateRequest {
  name: string;
  contact_email: string | null;
  contact_phone: string | null;
  supplier_type: string | null;
  entity_type: string | null;
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
  billing_email: string | null;
}

export interface ClientCreateRequest {
  name: string;
  code: string | null;
  address: string | null;
  contact_name: string | null;
  contact_email: string | null;
  billing_email: string | null;
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
  category_level: string;
  parent_id: string | null;
  description: string | null;
}

export interface ProjectTypeCreateRequest {
  name: string;
  code: string | null;
  category_level: string;
  parent_id: string | null;
  description: string | null;
}

export interface ProjectTypeTreeItem {
  id: string;
  name: string;
  code: string | null;
  category_level: string;
  parent_id: string | null;
  description: string | null;
  selectable: boolean;
  children: ProjectTypeTreeItem[];
}

export interface ProjectTypeTreeResponse {
  items: ProjectTypeTreeItem[];
}

export interface RegistrationDedupeCandidateItem {
  target_type: string;
  target_id: string;
  display_name: string;
  match_reasons: string[];
  phone: string | null;
  email: string | null;
  entity_type: string | null;
  notes: string | null;
  field_differences: RegistrationFieldDifferenceItem[];
}

export interface RegistrationFieldDifferenceItem {
  field_name: string;
  field_label: string;
  request_value: string | null;
  existing_value: string | null;
  is_match: boolean;
}

export interface RegistrationRequestFileItem {
  id: string;
  document_type: string;
  document_part: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  scan_status: string;
  uploaded_at: string;
  delete_after: string | null;
  deleted_at: string | null;
}

export interface RegistrationRequestListItem {
  id: string;
  request_type: string;
  status: string;
  source_type: string;
  summary_name: string | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  reviewed_by: string | null;
  approved_target_type: string | null;
  approved_target_id: string | null;
  expires_at: string | null;
  failed_attempts: number;
  locked_at: string | null;
  dedupe_key: string | null;
  notes: string | null;
}

export interface RegistrationRequestDetailResponse {
  id: string;
  request_type: string;
  status: string;
  source_type: string;
  summary_name: string | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  reviewed_by: string | null;
  reviewed_by_name: string | null;
  approved_target_type: string | null;
  approved_target_id: string | null;
  expires_at: string | null;
  failed_attempts: number;
  locked_at: string | null;
  dedupe_key: string | null;
  superseded_by_request_id: string | null;
  submitted_ip: string | null;
  user_agent: string | null;
  notes: string | null;
  detail_data: Record<string, unknown> | null;
  dedupe_candidates: RegistrationDedupeCandidateItem[];
  files: RegistrationRequestFileItem[];
}

export interface RegistrationLinkCreateRequest {
  request_type: "worker" | "supplier_individual" | "supplier_corporation" | "introducer_identity";
  expires_in_days: number;
  notes: string | null;
}

export interface RegistrationLinkResponse {
  request_id: string;
  request_type: string;
  status: string;
  expires_at: string;
  public_form_url: string;
  public_token: string;
  access_pin: string;
  failed_attempts: number;
  locked_at: string | null;
  notes: string | null;
}

export interface PublicRegistrationAccessResponse {
  request_id: string;
  request_type: string;
  status: string;
  expires_at: string | null;
  failed_attempts: number;
  detail_data: Record<string, unknown> | null;
  files: RegistrationRequestFileItem[];
}

export interface PublicRegistrationSubmitResponse {
  request_id: string;
  request_type: string;
  status: string;
  submitted_at: string;
  dedupe_key: string | null;
}

export interface PublicRegistrationFileUploadResponse {
  file: RegistrationRequestFileItem;
  files: RegistrationRequestFileItem[];
}

export interface PublicWorkerRegistrationSubmitRequest {
  token: string;
  pin: string;
  last_name: string | null;
  first_name: string | null;
  last_name_furigana: string | null;
  first_name_furigana: string | null;
  sole_proprietor_name: string | null;
  gender: string | null;
  route_group: string | null;
  introducer_supplier_name_raw: string | null;
  email: string | null;
  phone: string | null;
  zipcode: string | null;
  prefecture: string | null;
  city_address: string | null;
  building_address: string | null;
  emergency_contact_name_kana: string | null;
  emergency_contact_phone: string | null;
  bank_name: string | null;
  bank_branch: string | null;
  bank_branch_number: string | null;
  bank_account_type: string | null;
  bank_account_number: string | null;
  bank_account_holder: string | null;
  invoice_registration_status: string | null;
  invoice_registration_number: string | null;
  memo: string | null;
}

export interface PublicSupplierIndividualRegistrationSubmitRequest {
  token: string;
  pin: string;
  supplier_type: string | null;
  name: string | null;
  name_furigana: string | null;
  trade_name: string | null;
  email: string | null;
  phone: string | null;
  zipcode: string | null;
  prefecture: string | null;
  city_address: string | null;
  building_address: string | null;
  bank_name: string | null;
  bank_branch: string | null;
  bank_branch_number: string | null;
  bank_account_type: string | null;
  bank_account_number: string | null;
  bank_account_holder_kana: string | null;
  invoice_registration_status: string | null;
  invoice_registration_number: string | null;
  memo: string | null;
}

export interface PublicSupplierCorporationRegistrationSubmitRequest {
  token: string;
  pin: string;
  supplier_type: string | null;
  company_name: string | null;
  company_name_furigana: string | null;
  representative_name: string | null;
  representative_name_furigana: string | null;
  email: string | null;
  phone: string | null;
  zipcode: string | null;
  prefecture: string | null;
  city_address: string | null;
  building_address: string | null;
  bank_name: string | null;
  bank_branch: string | null;
  bank_branch_number: string | null;
  bank_account_type: string | null;
  bank_account_number: string | null;
  bank_account_holder_kana: string | null;
  invoice_registration_status: string | null;
  invoice_registration_number: string | null;
  memo: string | null;
}

export interface PublicIntroducerIdentityRegistrationSubmitRequest {
  token: string;
  pin: string;
  related_worker_request_id: string | null;
  related_supplier_request_id: string | null;
  subject_name: string | null;
  subject_name_furigana: string | null;
  submission_reason: string | null;
  memo: string | null;
}

export interface RegistrationRequestApproveRequest {
  approved_target_id: string | null;
  dedupe_resolution: "create_new" | "merge_existing" | null;
  notes: string | null;
}

export interface RegistrationRequestRejectRequest {
  reason: string;
  notes: string | null;
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

// ===========================
// Staff Notice
// ===========================

export type NoticeType = "shift_confirm" | "project_change" | "general";
export type NoticePriority = "normal" | "urgent";
export type NoticeTargetType = "all" | "project" | "worker";

export interface NoticeCreateRequest {
  title: string;
  body: string;
  notice_type: NoticeType;
  priority: NoticePriority;
  target_type: NoticeTargetType;
  target_project_id?: string | null;
  target_worker_ids?: string[] | null;
  send_email: boolean;
  /** push通知アクションボタン: "ok_ng" | "confirm" | null */
  push_action_type?: string | null;
}

export interface NoticeListItem {
  id: string;
  title: string;
  notice_type: NoticeType;
  priority: NoticePriority;
  target_type: NoticeTargetType;
  target_project_id: string | null;
  target_project_name: string | null;
  target_worker_ids: string[] | null;
  send_email: boolean;
  push_action_type: string | null;
  sent_at: string | null;
  read_count: number;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
  deleted_at: string | null;
}

export interface NoticeListResponse {
  items: NoticeListItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface WorkerNoticeItem {
  id: string;
  title: string;
  body: string;
  notice_type: NoticeType;
  priority: NoticePriority;
  target_project_id: string | null;
  target_project_name: string | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface WorkerNoticeListResponse {
  items: WorkerNoticeItem[];
  unread_count: number;
  total: number;
}

// ===========================
// VanzaiStaff
// ===========================

export interface VanzaiStaffItem {
  id: string;
  name: string;
  role: string | null;
  linked_worker_id: string | null;
  linked_worker_name: string | null;
  playing_manager_fee_type: "subordinate_man_days" | "fixed_amount" | null;
  playing_manager_fixed_fee: string | null;
  phone: string | null;
  email: string | null;
  is_active: boolean;
  notes: string | null;
}

export interface VanzaiStaffCreateRequest {
  name: string;
  role: string | null;
  linked_worker_id: string | null;
  playing_manager_fee_type: "subordinate_man_days" | "fixed_amount" | null;
  playing_manager_fixed_fee: string | null;
  phone: string | null;
  email: string | null;
  is_active: boolean;
  notes: string | null;
}

export interface VanzaiStaffUpdateRequest extends VanzaiStaffCreateRequest {}

// ===========================
// ClientStaff
// ===========================

export interface ClientStaffItem {
  id: string;
  client_id: string;
  name: string;
  role: string | null;
  phone: string | null;
  email: string | null;
  is_active: boolean;
  notes: string | null;
}

export interface ClientStaffCreateRequest {
  name: string;
  role: string | null;
  phone: string | null;
  email: string | null;
  is_active: boolean;
  notes: string | null;
}

export interface ClientStaffUpdateRequest extends ClientStaffCreateRequest {}

// ===========================
// WorkerBankAccount
// ===========================

export interface WorkerBankAccountItem {
  id: string;
  worker_id: string;
  bank_name: string;
  branch_name: string;
  branch_code: string | null;
  account_type: string;
  account_number: string;
  account_holder_kana: string;
  transfer_destination_name: string | null;
  effective_from: string;
  effective_until: string | null;
  is_primary: boolean;
}

export interface WorkerBankAccountListResponse {
  items: WorkerBankAccountItem[];
  total: number;
}

export interface WorkerBankAccountCreateRequest {
  bank_name: string;
  branch_name: string;
  branch_code: string | null;
  account_type: string;
  account_number: string;
  account_holder_kana: string;
  transfer_destination_name: string | null;
  effective_from: string;
  effective_until: string | null;
  is_primary: boolean;
}

export interface WorkerBankAccountUpdateRequest extends WorkerBankAccountCreateRequest {}

// ===========================
// SupplierBankAccount
// ===========================

export interface SupplierBankAccountItem {
  id: string;
  supplier_id: string;
  bank_name: string;
  branch_name: string;
  branch_code: string | null;
  account_type: string;
  account_number: string;
  account_holder_kana: string;
  transfer_destination_name: string | null;
  effective_from: string;
  effective_until: string | null;
  is_primary: boolean;
}

export interface SupplierBankAccountListResponse {
  items: SupplierBankAccountItem[];
  total: number;
}

export interface SupplierBankAccountCreateRequest {
  bank_name: string;
  branch_name: string;
  branch_code: string | null;
  account_type: string;
  account_number: string;
  account_holder_kana: string;
  transfer_destination_name: string | null;
  effective_from: string;
  effective_until: string | null;
  is_primary: boolean;
}

export interface SupplierBankAccountUpdateRequest extends SupplierBankAccountCreateRequest {}

// ===========================
// OCR Receipt
// ===========================

export type OcrSourceType = "paygate_screenshot" | "paygate_settlement";

export interface OcrSourceImageItem {
  id: string;
  source_type: OcrSourceType;
  original_filename: string | null;
  sha256: string;
  mime_type: string | null;
  size_bytes: number;
  period_key: string | null;
  parse_status: string;
  uploaded_by: string | null;
  last_job_id: string | null;
  error_message: string | null;
  created_at: string;
  reused_existing?: boolean;
  has_filename_duplicate?: boolean;
}

export interface OcrSourceImageListResponse {
  items: OcrSourceImageItem[];
  total: number;
}

export interface OcrParseJobResponse {
  id: string;
  status: string;
  image_count: number;
  success_count: number;
  failed_count: number;
  row_count: number;
  executed_by: string | null;
  completed_at: string | null;
}

export interface OcrExtractedRowItem {
  id: string;
  source_image_id: string;
  source_image_filename: string | null;
  parse_job_id: string | null;
  source_type: OcrSourceType;
  period_key: string | null;
  record_date: string | null;
  record_time: string | null;
  amount: string | null;
  currency: string;
  transaction_no: string | null;
  receipt_no: string | null;
  payment_method: string | null;
  terminal_id: string | null;
  cash_sales: string | null;
  credit_sales: string | null;
  transaction_count: number | null;
  tax_included: string | null;
  subtotal: string | null;
  store_name: string | null;
  confidence: string | null;
  amount_inferred: boolean;
  amount_source: string | null;
  datetime_source: string | null;
  confirm_required: boolean;
  manually_edited: boolean;
  status: string;
  validation_errors: string[] | null;
  project_id: string | null;
  report_date: string | null;
  linked_entity_type: string | null;
  linked_entity_id: string | null;
  confirmed_at: string | null;
  confirmed_by: string | null;
  // --- paygate_settlement 専用項目（計画書 v4） ---
  terminal_short_id: string | null;
  pos_sales: string | null;
  other_payment: string | null;
  cash_unit_count: number | null;
  pos_unit_count: number | null;
  work_date: string | null;
  unit_breakdown_status: string | null;
  unit_breakdown_json: Record<string, number | null> | null;
  amount_ones_digit_ok: boolean | null;
  blocking_errors: string[] | null;
  warnings: string[] | null;
  duplicate_receipt_candidate: boolean;
  reconciliation_eligible: boolean;
  excluded_reason: string | null;
  voided_at: string | null;
  voided_by: string | null;
  void_reason: string | null;
  branch_id: string | null;
  staff_id: string | null;
  field_confidence?: Record<string, number> | null;
  field_sources?: Record<string, string> | null;
}

export interface OcrExtractedRowListResponse {
  items: OcrExtractedRowItem[];
  total: number;
}

// ===========================
// Inventory Reconciliation (計画書 v4 Phase 2)
// ===========================

export interface InventorySnapshotItem {
  id: string;
  branch_id: string;
  terminal_short_id: string;
  work_date: string;
  staff_id: string | null;
  opening_count: number;
  closing_count: number;
  adjustment_count: number;
  adjustment_reason: string | null;
  inventory_decrease: number;
  entered_by: string;
  entered_at: string;
  confirmed_by: string | null;
  confirmed_at: string | null;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface InventorySnapshotListResponse {
  items: InventorySnapshotItem[];
  total: number;
}

export interface InventorySnapshotCreateRequest {
  branch_id: string;
  terminal_short_id: string;
  work_date: string;
  staff_id?: string | null;
  opening_count: number;
  closing_count: number;
  adjustment_count?: number;
  adjustment_reason?: string | null;
  note?: string | null;
}

export interface InventorySnapshotUpdateRequest {
  staff_id?: string | null;
  opening_count?: number;
  closing_count?: number;
  adjustment_count?: number;
  adjustment_reason?: string | null;
  note?: string | null;
}

export interface InventoryReconciliationResultItem {
  id: string;
  batch_id: string;
  branch_id: string;
  terminal_short_id: string;
  work_date: string;
  ocr_row_id: string | null;
  inventory_snapshot_id: string | null;
  ocr_transaction_count: number | null;
  inventory_decrease: number | null;
  diff: number | null;
  match_status: string;
  diff_reason_category: string | null;
  notes: string | null;
}

export interface InventoryReconciliationBatchResponse {
  id: string;
  period_key: string | null;
  date_from: string | null;
  date_to: string | null;
  executed_by: string | null;
  total_count: number;
  matched_count: number;
  adjusted_matched_count: number;
  count_mismatch_count: number;
  sales_only_count: number;
  inventory_only_count: number;
  excluded_count: number;
  results: InventoryReconciliationResultItem[];
}

export interface OcrMonthlySummaryItem {
  period_key: string;
  source_type: string;
  row_count: number;
  total_amount: string;
}

export interface OcrMonthlySummaryResponse {
  items: OcrMonthlySummaryItem[];
}

export interface OcrReconciliationResultItem {
  id: string;
  match_status: string;
  ocr_row_id: string | null;
  hq_row_index: number | null;
  hq_payload: Record<string, string> | null;
  amount_diff: string | null;
  notes: string | null;
}

export interface OcrReconciliationBatchResponse {
  id: string;
  period_key: string | null;
  file_name: string;
  row_count: number;
  matched_count: number;
  unmatched_ocr_count: number;
  unmatched_hq_count: number;
  amount_diff_count: number;
  results: OcrReconciliationResultItem[];
}

export interface OcrSelfReportCompareResponse {
  period_key: string;
  project_id: string | null;
  ocr_row_count: number;
  ocr_total_amount: string;
  linked_count: number;
  self_report_available: boolean;
  message: string;
}
