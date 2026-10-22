export type OrderRequestKind = "formal" | "test";
export type OrderRequestStatus = "draft" | "confirmed" | "cancelled";
export type OrderRequestQueue = "all" | "unsent" | "unknown" | "unacked" | "overdue";

export interface InternalOrderSource {
  client_id: string;
  client_staff_id: string | null;
  client_name?: string;
  client_phone?: string | null;
  staff_name?: string | null;
  staff_phone?: string | null;
}

export interface OrderRequestDelivery {
  id: string;
  worker_id: string;
  worker_name_snapshot: string;
  send_status: string;
  ack_status: string;
  acked_at: string | null;
  decline_reason: string | null;
  ack_reminded_at: string | null;
  view_revoked: boolean;
  line_linked: boolean;
  line_display_name: string | null;
  last_send_error: string | null;
  /** 確定時に決まったこの人の提示日。NULL は日程のない依頼書（稼働予定の対象外）。 */
  offered_dates: string[] | null;
  /** この送付行が、系列で今の稼働予定の元になっている受諾か。 */
  applied: boolean;
  /** 系列で、この人に参加日が残っているか（受諾後の辞退を記録できるか）。 */
  participating: boolean;
  participation_dates: string[];
  /** 「今後の参加を終了」で取り消す日があるか（勤務が始まっていない参加日がある） */
  can_end_participation: boolean;
  /** 「今後の参加を終了」で残る日・取り消される日。受諾がなければ null */
  end_preview: { kept_dates: string[]; removed_dates: string[]; today_removed_start: string | null } | null;
}

export interface WakeStatusEntry {
  id: string;
  document_id: string;
  start_time: string | null;
  end_time: string | null;
  end_next_day: boolean;
  project_name: string;
  site_name: string;
  meeting_place: string | null;
  status: "active" | "changing";
}

export interface WakeStatusItem {
  worker_id: string;
  worker_name: string;
  line_linked: boolean;
  first_start: string | null;
  overlap_warning: boolean;
  entries: WakeStatusEntry[];
  wake_reported_at: string | null;
  wake_late_received: boolean;
}

export interface WakeStatusList {
  date: string;
  total: number;
  reported: number;
  items: WakeStatusItem[];
}

export interface LineWorkerLinkItem {
  worker_id: string;
  worker_name: string;
  line_display_name: string | null;
  linked_at: string;
}

export interface LineLinkList {
  line_send_available: boolean;
  purpose: string;
  unlink_notice: string;
  items: LineWorkerLinkItem[];
}

export interface LineLinkCode {
  worker_id: string;
  worker_name: string;
  code: string;
  expires_at: string;
  instruction: string;
  purpose: string;
  unlink_notice: string;
}

export interface OrderRequestChangeLink {
  version_id: string;
  document_number: string;
  version_no: number;
  status: OrderRequestStatus;
}

export interface OrderRequestNote {
  id: string;
  author_user_id: string;
  author_name: string | null;
  body: string;
  created_at: string;
}

export interface OrderRequestVersion {
  internal_source?: InternalOrderSource | null;
  document_id: string;
  document_number: string;
  kind: OrderRequestKind;
  id: string;
  version_no: number;
  status: OrderRequestStatus;
  revision_of_version_id: string | null;
  revision_reason: string | null;
  based_on_document_number: string | null;
  based_on_version_no: number | null;
  change_documents: OrderRequestChangeLink[];
  work_date_label: string;
  site_id: string | null;
  site_name: string;
  site_address: string | null;
  request_conditions: string;
  body: string;
  contact_name: string;
  contact_desk: string;
  counterparty_note: string | null;
  draft_worker_ids: string[];
  /** 送付先ごとの個人不参加日（DEC-065）。 */
  draft_recipient_absences?: Record<string, string[]>;
  allow_partial_accept: boolean;
  phone_first: boolean;
  phone_contacted_at: string | null;
  phone_note: string | null;
  tracker_user_id: string | null;
  tracker_name: string | null;
  follow_up_due_on: string | null;
  follow_up_due_time: string;
  confirmed_at: string | null;
  confirmed_by_name: string | null;
  cancelled_at: string | null;
  cancel_reason: string | null;
  dispatch_stopped: boolean;
  created_by_name: string | null;
  has_pdf: boolean;
  template_layout_applied: boolean;
  line_send_available: boolean;
  deliveries: OrderRequestDelivery[];
  notes: OrderRequestNote[];
  created_at: string;
  updated_at: string;
}

export interface OrderRequestListItem {
  document_id: string;
  document_number: string;
  kind: OrderRequestKind;
  based_on_document_number: string | null;
  based_on_version_no: number | null;
  change_documents: OrderRequestChangeLink[];
  version_id: string;
  version_no: number;
  status: OrderRequestStatus;
  project_name: string;
  site_name: string;
  work_date_label: string;
  created_by_name: string | null;
  tracker_name: string | null;
  recipient_count: number;
  unsent_count: number;
  unacked_count: number;
  acked_count: number;
  phone_first: boolean;
  follow_up_due_on: string | null;
  follow_up_due_time: string;
  dispatch_stopped: boolean;
  cancel_reason: string | null;
  has_pdf: boolean;
  template_layout_applied: boolean;
  line_send_available: boolean;
  confirmed_at: string | null;
}

export interface DeletedOrderRequestListItem extends OrderRequestListItem {
  deleted_at: string | null;
  deleted_by_name: string | null;
}

export interface DeletedOrderRequestListResponse {
  items: DeletedOrderRequestListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface OrderRequestListResponse {
  items: OrderRequestListItem[];
  total: number;
  limit: number;
  offset: number;
  template_layout_applied: boolean;
  line_send_available: boolean;
}

export interface OrderRequestReplyItem {
  delivery_id: string;
  version_id: string;
  document_number: string;
  version_no: number;
  based_on_document_number: string | null;
  based_on_version_no: number | null;
  change_documents: OrderRequestChangeLink[];
  kind: string;
  project_name: string;
  site_name: string;
  work_date_label: string;
  worker_name: string;
  send_status: string;
  ack_status: string;
  decline_reason: string | null;
  acked_at: string | null;
  follow_up_due_on: string | null;
  ack_reminded_at: string | null;
}

export interface OrderRequestReplyList {
  items: OrderRequestReplyItem[];
}

export interface OrderRequestWrite {
  internal_source?: InternalOrderSource | null;
  kind: OrderRequestKind;
  work_date_label: string;
  site_id: string | null;
  site_name: string;
  site_address: string | null;
  request_conditions: string;
  body: string;
  contact_name: string;
  contact_desk: string;
  counterparty_note: string | null;
  worker_ids: string[];
  phone_first: boolean;
  phone_note: string | null;
  tracker_user_id?: string | null;
  follow_up_due_on: string | null;
  follow_up_due_time: string;
  assign_tracker_self?: boolean;
  based_on_version_id?: string | null;
  /** 送付先ごとの個人不参加日（DEC-065）。 */
  recipient_absences?: Record<string, string[]>;
  /** 日付を選んで受諾できる（A1+ §3.1） */
  allow_partial_accept?: boolean;
}
