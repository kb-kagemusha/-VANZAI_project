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

export interface PageResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
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
  worker_response_status: string | null;
  worker_response_requested_at: string | null;
  worker_response_at: string | null;
  worker_response_note: string | null;
  locked_price_sales: string | null;
  locked_price_outsource: string | null;
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

export interface AttendanceRecord {
  actual_id: string;
  assignment_id: string;
  project_id: string;
  project_name: string;
  worker_id: string;
  worker_name: string;
  role_id: string;
  role_name: string;
  work_date: string;
  start_time: string | null;
  end_time: string | null;
  break_minutes_input: number | null;
  calc_minutes_billable: number;
  status: string;
  import_batch_id: string;
  import_batch_file_name: string;
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

export interface ExpenseSubmissionResponse {
  id: string;
  expense_date: string;
  project_id: string;
  project_name: string;
  worker_id: string | null;
  worker_name: string;
  category: string;
  amount: string;
  description: string | null;
  status: string;
  reject_reason: string | null;
  has_receipt: boolean;
}

export interface WorkerAvailabilityListItem {
  id: string;
  worker_id: string;
  worker_name: string;
  availability_date: string;
  status: string;
  notes: string | null;
  updated_at: string;
}

export interface WorkerAvailabilityPreference {
  worker_id: string;
  weekly_default_statuses: Record<string, string>;
  holiday_default_status: string | null;
  auto_apply_enabled: boolean;
  updated_at: string | null;
}

// Staff Notice
export type NoticeType = "shift_confirm" | "project_change" | "general";
export type NoticePriority = "normal" | "urgent";

export interface WorkerNoticeItem {
  id: string;
  title: string;
  body: string;
  notice_type: NoticeType;
  priority: NoticePriority;
  target_project_id: string | null;
  target_project_name: string | null;
  /** push通知アクションボタン種別: "ok_ng" | "confirm" | null */
  push_action_type: string | null;
  is_read: boolean;
  read_at: string | null;
  /** 返答状態: "ok" | "ng" | null(未回答) */
  response: "ok" | "ng" | null;
  responded_at: string | null;
  created_at: string;
}

export interface WorkerNoticeListResponse {
  items: WorkerNoticeItem[];
  unread_count: number;
  total: number;
}