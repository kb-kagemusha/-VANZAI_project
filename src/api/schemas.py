"""
APIリクエスト・レスポンスのPydanticスキーマ定義
"""
from datetime import date, datetime
from typing import Generic, List, Literal, Optional, TypeVar

from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from decimal import Decimal

DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200

SchemaT = TypeVar("SchemaT")


# ===========================
# Common List Schemas
# ===========================

class PaginationQuery(BaseModel):
    """一覧系APIの共通ページングクエリ"""
    offset: int = Field(0, ge=0)
    limit: int = Field(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)


class SortQuery(BaseModel):
    """一覧系APIの共通ソートクエリ"""
    sort_by: Optional[str] = None
    sort_order: Literal["asc", "desc"] = "desc"


class PageResponse(BaseModel, Generic[SchemaT]):
    """一覧系APIの共通レスポンス"""
    items: List[SchemaT]
    total: int = Field(..., ge=0)
    offset: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)

# ===========================
# CSV Import Schemas
# ===========================

class CSVImportRequest(BaseModel):
    """CSV取り込みリクエスト"""
    file_content: str = Field(..., description="Base64エンコードされたCSVファイル内容")
    file_name: str = Field(..., description="ファイル名")
    project_id: str = Field(..., description="案件ID")
    period_key: str = Field(..., description="対象期間キー（YYYYMM）")
    import_mode: str = Field("replace_scope", description="取り込みモード: append, replace_scope")
    scope_type: Optional[str] = Field("project_month", description="洗い替えスコープタイプ")


class CSVImportResponse(BaseModel):
    """CSV取り込みレスポンス"""
    batch_id: str
    status: str
    total_rows: int
    success_rows: int
    error_rows: int
    skipped_rows: int
    superseded_rows: int
    warnings: List[str] = Field(default_factory=list)
    errors: Optional[List[dict]] = None


class ImportBatchListQuery(PaginationQuery, SortQuery):
    """CSV取り込み履歴クエリ"""
    period_key: Optional[str] = Field(None, pattern=r"^\d{6}$")
    project_id: Optional[str] = None
    status: Optional[str] = None
    search: Optional[str] = Field(None, max_length=100)


class ImportBatchListItem(BaseModel):
    """CSV取り込み履歴の1行"""
    id: str
    file_name: str
    project_id: Optional[str] = None
    project_name: str
    period_key: str
    submitted_by: Optional[str] = None
    submit_channel: str
    mode: str
    scope_type: Optional[str] = None
    status: str
    success_rows: int
    error_rows: int
    skipped_rows: int
    superseded_rows: int
    has_warnings: bool
    errors_preview: List[dict] = Field(default_factory=list)
    created_at: datetime


class ImportBatchListResponse(PageResponse[ImportBatchListItem]):
    """CSV取り込み履歴レスポンス"""
    pass


# ===========================
# Dashboard Schemas
# ===========================

class UnprocessedItem(BaseModel):
    """未処理項目"""
    item_type: str
    count: int
    details: List[dict]


class VarianceAlert(BaseModel):
    """差異アラート"""
    project_name: str
    worker_name: str
    work_date: date
    planned_minutes: int
    actual_minutes: int
    variance_minutes: int


class ClosingStatusItem(BaseModel):
    """締め状況"""
    project_id: str
    period_key: str
    project_name: str
    status: str
    closed_at: Optional[datetime]
    closed_by: Optional[str]
    release_count: int = 0
    last_released_at: Optional[datetime] = None
    last_released_by: Optional[str] = None
    reclose_deadline: Optional[datetime] = None


class DashboardResponse(BaseModel):
    """ダッシュボードレスポンス"""
    unprocessed_items: List[UnprocessedItem]
    variance_alerts: List[VarianceAlert]
    closing_status: List[ClosingStatusItem]


# ===========================
# Actuals List Schemas
# ===========================

class ActualListQuery(PaginationQuery, SortQuery):
    """実績一覧クエリ"""
    project_id: Optional[str] = None
    worker_id: Optional[str] = None
    status: Optional[str] = None
    needs_review: Optional[bool] = None
    period_key: Optional[str] = Field(None, pattern=r"^\d{6}$")
    work_date_from: Optional[date] = None
    work_date_to: Optional[date] = None
    import_batch_id: Optional[str] = None


class ActualListItem(BaseModel):
    """実績一覧の1行"""
    id: str
    project_id: str
    project_name: str
    worker_id: str
    worker_name: str
    role_id: str
    role_name: str
    assignment_id: Optional[str] = None
    import_batch_id: str
    import_batch_file_name: str
    work_date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    calc_minutes_billable: int
    applied_price_sales: Decimal
    applied_price_outsource: Decimal
    status: str
    needs_review: bool
    review_reason: Optional[str] = None
    external_row_key: Optional[str] = None


class ActualListResponse(PageResponse[ActualListItem]):
    """実績一覧レスポンス"""
    pass


# ===========================
# Assignments List Schemas
# ===========================

class AssignmentListQuery(PaginationQuery, SortQuery):
    """アサイン一覧クエリ"""
    project_id: Optional[str] = None
    worker_id: Optional[str] = None
    role_id: Optional[str] = None
    status: Optional[str] = None
    response_status: Optional[str] = None
    monitoring_status: Optional[Literal["watch", "escalate"]] = None
    missing_email_only: bool = False
    work_date_from: Optional[date] = None
    work_date_to: Optional[date] = None


class AssignmentListItem(BaseModel):
    """アサイン一覧の1行"""
    id: str
    shift_slot_id: str
    project_id: str
    project_name: str
    work_date: date
    shift_label: Optional[str] = None
    worker_id: str
    worker_name: str
    worker_email: Optional[str] = None
    role_id: str
    role_name: str
    status: str
    cancel_reason: Optional[str] = None
    worker_response_status: Optional[str] = None
    worker_response_requested_at: Optional[datetime] = None
    worker_response_at: Optional[datetime] = None
    worker_response_note: Optional[str] = None
    monitoring_status: Optional[str] = None
    monitoring_reasons: List[str] = Field(default_factory=list)
    hours_since_response_request: Optional[int] = None
    days_until_work: Optional[int] = None
    locked_price_sales: Optional[Decimal] = None
    locked_price_outsource: Optional[Decimal] = None


class AssignmentListResponse(PageResponse[AssignmentListItem]):
    """アサイン一覧レスポンス"""
    pass


class AssignmentReminderSendRequest(BaseModel):
    """予定確認催促送信リクエスト"""
    assignment_ids: List[str] = Field(default_factory=list, min_length=1)
    dry_run: Optional[bool] = None


class AssignmentReminderSendWorkerResult(BaseModel):
    """予定確認催促送信の worker 単位結果"""
    worker_id: str
    worker_name: str
    worker_email: Optional[str] = None
    assignment_ids: List[str] = Field(default_factory=list)
    assignment_count: int
    status: Literal["sent", "failed", "skipped_missing_email"]


class AssignmentReminderSendResponse(BaseModel):
    """予定確認催促送信レスポンス"""
    requested_assignment_count: int
    eligible_assignment_count: int
    recipient_count: int
    sent_count: int
    failed_count: int
    skipped_missing_email_count: int
    dry_run: bool
    worker_results: List[AssignmentReminderSendWorkerResult] = Field(default_factory=list)


class AssignmentReminderHistoryRequest(BaseModel):
    """予定確認催促履歴取得リクエスト"""
    assignment_ids: List[str] = Field(default_factory=list, min_length=1)
    limit: int = Field(20, ge=1, le=100)


class AssignmentReminderHistoryItem(BaseModel):
    """予定確認催促履歴の1行"""
    audit_log_id: str
    created_at: datetime
    actor: Optional[str] = None
    actor_role: Optional[str] = None
    worker_id: Optional[str] = None
    worker_name: str
    worker_email: Optional[str] = None
    status: Literal["sent", "failed"]
    dry_run: bool
    assignment_ids: List[str] = Field(default_factory=list)
    assignment_count: int


class AssignmentReminderHistoryResponse(BaseModel):
    """予定確認催促履歴レスポンス"""
    items: List[AssignmentReminderHistoryItem] = Field(default_factory=list)


class AssignmentEscalationSendRequest(BaseModel):
    """予定確認エスカレーション通知リクエスト"""
    assignment_ids: List[str] = Field(default_factory=list, min_length=1)
    dry_run: Optional[bool] = None


class AssignmentEscalationHistoryRequest(BaseModel):
    """予定確認エスカレーション履歴取得リクエスト"""
    assignment_ids: List[str] = Field(default_factory=list, min_length=1)
    limit: int = Field(20, ge=1, le=100)


class AssignmentEscalationHistoryItem(BaseModel):
    """予定確認エスカレーション履歴の1行"""
    audit_log_id: str
    created_at: datetime
    actor: Optional[str] = None
    actor_role: Optional[str] = None
    recipient_name: str
    recipient_email: str
    status: Literal["sent", "failed"]
    dry_run: bool
    assignment_ids: List[str] = Field(default_factory=list)
    assignment_count: int


class AssignmentEscalationHistoryResponse(BaseModel):
    """予定確認エスカレーション履歴レスポンス"""
    items: List[AssignmentEscalationHistoryItem] = Field(default_factory=list)


class AssignmentEscalationRecipientResult(BaseModel):
    """予定確認エスカレーション通知の recipient 単位結果"""
    recipient_email: str
    recipient_name: str
    escalated_assignment_count: int
    status: Literal["sent", "failed"]


class AssignmentEscalationSendResponse(BaseModel):
    """予定確認エスカレーション通知レスポンス"""
    requested_assignment_count: int
    eligible_assignment_count: int
    recipient_count: int
    sent_count: int
    failed_count: int
    dry_run: bool
    recipient_results: List[AssignmentEscalationRecipientResult] = Field(default_factory=list)


class AssignmentCancellationHistoryQuery(PaginationQuery, SortQuery):
    """アサイン取消履歴クエリ"""
    project_id: Optional[str] = None
    work_date_from: Optional[date] = None
    work_date_to: Optional[date] = None


class AssignmentCancellationHistoryItem(BaseModel):
    """アサイン取消履歴の1行"""
    audit_log_id: str
    assignment_id: str
    project_id: str
    project_name: str
    work_date: date
    shift_label: Optional[str] = None
    worker_id: str
    worker_name: str
    role_id: str
    role_name: str
    canceled_at: datetime
    canceled_by: Optional[str] = None
    cancel_reason: Optional[str] = None
    reopened_at: Optional[datetime] = None
    reopened_by: Optional[str] = None
    reopen_reason: Optional[str] = None
    current_status: str


class AssignmentCancellationHistoryResponse(PageResponse[AssignmentCancellationHistoryItem]):
    """アサイン取消履歴レスポンス"""
    pass


class AssignmentSelectionSetListQuery(BaseModel):
    """アサイン選択セット一覧クエリ"""
    period_key: str = Field(..., pattern=r"^\d{6}$")


class AssignmentSelectionSetItem(BaseModel):
    """アサイン選択セットの1件"""
    id: str
    name: str
    period_key: str
    assignment_ids: List[str]
    total_assignment_count: int
    available_assignment_count: int
    is_shared: bool
    created_at: datetime
    created_by: Optional[str] = None
    editable: bool


class AssignmentSelectionSetListResponse(BaseModel):
    """アサイン選択セット一覧レスポンス"""
    items: List[AssignmentSelectionSetItem]


class AssignmentSelectionSetCreateRequest(BaseModel):
    """アサイン選択セット作成リクエスト"""
    name: str = Field(..., min_length=1, max_length=120)
    period_key: str = Field(..., pattern=r"^\d{6}$")
    assignment_ids: List[str] = Field(..., min_length=1, max_length=200)
    is_shared: bool = False


class AssignmentCreateRequest(BaseModel):
    """アサイン作成リクエスト"""
    shift_slot_id: str
    worker_id: str
    role_id: str
    status: Literal["tentative", "confirmed", "canceled"] = "tentative"
    cancel_reason: Optional[str] = None
    locked_price_sales: Optional[Decimal] = None
    locked_price_outsource: Optional[Decimal] = None


class AssignmentUpdateRequest(BaseModel):
    """アサイン更新リクエスト"""
    shift_slot_id: str
    worker_id: str
    role_id: str
    locked_price_sales: Optional[Decimal] = None
    locked_price_outsource: Optional[Decimal] = None


class AssignmentBulkStatusUpdateRequest(BaseModel):
    """アサイン一括状態更新リクエスト"""
    assignment_ids: List[str] = Field(..., min_length=1, max_length=100)
    status: Literal["tentative", "confirmed", "canceled"]
    cancel_reason: Optional[str] = None
    reopen_reason: Optional[str] = None


class AssignmentStatusUpdateRequest(BaseModel):
    """アサイン状態更新リクエスト"""
    status: Literal["tentative", "confirmed", "canceled"]
    cancel_reason: Optional[str] = None
    reopen_reason: Optional[str] = None


class AssignmentWorkerResponseUpdateRequest(BaseModel):
    """稼働者による予定確認応答リクエスト"""
    response_status: Literal["accepted", "declined"]
    note: Optional[str] = Field(None, max_length=2000)


class AssignmentBulkMutationResponse(BaseModel):
    """アサイン一括更新レスポンス"""
    updated_count: int
    assignment_ids: List[str]
    status: str


# ===========================
# Projects List Schemas
# ===========================

class ProjectListQuery(PaginationQuery, SortQuery):
    """案件一覧クエリ"""
    client_id: Optional[str] = None
    site_id: Optional[str] = None
    project_type_id: Optional[str] = None
    is_active: Optional[bool] = None
    search: Optional[str] = None


class ProjectListItem(BaseModel):
    """案件一覧の1行"""
    id: str
    code: Optional[str] = None
    name: str
    client_id: Optional[str] = None
    client_name: str
    site_id: Optional[str] = None
    site_name: str
    project_type_id: Optional[str] = None
    project_type_name: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    primary_manager_id: Optional[str] = None
    secondary_manager_id: Optional[str] = None
    vanzai_manager_id: Optional[str] = None
    vanzai_manager_name: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool


class ProjectListResponse(PageResponse[ProjectListItem]):
    """案件一覧レスポンス"""
    pass


class ProjectCreateRequest(BaseModel):
    """案件作成リクエスト"""
    name: str = Field(..., min_length=1, max_length=200)
    code: Optional[str] = Field(None, max_length=50)
    client_id: str
    site_id: Optional[str] = None
    project_type_id: Optional[str] = None
    primary_manager_id: Optional[str] = None
    secondary_manager_id: Optional[str] = None
    vanzai_manager_id: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None
    is_active: bool = True


class ProjectUpdateRequest(ProjectCreateRequest):
    """案件更新リクエスト"""
    pass


class ProjectNotesUpdateRequest(BaseModel):
    """案件運用メモ更新リクエスト"""
    notes: Optional[str] = Field(None, max_length=2000)


# ===========================
# Shift Slots List Schemas
# ===========================

class ShiftSlotListQuery(PaginationQuery, SortQuery):
    """シフト枠一覧クエリ"""
    project_id: Optional[str] = None
    work_date_from: Optional[date] = None
    work_date_to: Optional[date] = None
    search: Optional[str] = None


class ShiftSlotListItem(BaseModel):
    """シフト枠一覧の1行"""
    id: str
    project_id: str
    project_name: str
    work_date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    shift_label: Optional[str] = None
    required_count: int
    assigned_count: int
    notes: Optional[str] = None


class ShiftSlotListResponse(PageResponse[ShiftSlotListItem]):
    """シフト枠一覧レスポンス"""
    pass


class ShiftSlotCreateRequest(BaseModel):
    """シフト枠作成リクエスト"""
    project_id: str
    work_date: date
    start_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}(:\d{2})?$")
    end_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}(:\d{2})?$")
    shift_label: Optional[str] = Field(None, max_length=50)
    required_count: int = Field(1, ge=1, le=999)
    notes: Optional[str] = None


class ShiftSlotUpdateRequest(ShiftSlotCreateRequest):
    """シフト枠更新リクエスト"""
    pass


class ShiftSlotNotesUpdateRequest(BaseModel):
    """シフト枠運用メモ更新リクエスト"""
    notes: Optional[str] = Field(None, max_length=2000)


# ===========================
# Attendance Schemas
# ===========================

class AttendanceActionRequest(BaseModel):
    """勤怠打刻リクエスト"""
    action_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}(:\d{2})?$")
    break_minutes_input: Optional[int] = Field(None, ge=0, le=720)
    notes: Optional[str] = Field(None, max_length=2000)


class AttendanceRecordResponse(BaseModel):
    """勤怠打刻レスポンス"""
    actual_id: str
    assignment_id: str
    project_id: str
    project_name: str
    worker_id: str
    worker_name: str
    role_id: str
    role_name: str
    work_date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    break_minutes_input: Optional[int] = None
    calc_minutes_billable: int
    status: str
    import_batch_id: str
    import_batch_file_name: str
    notes: Optional[str] = None


# ===========================
# Worker Availability Schemas
# ===========================

class WorkerAvailabilityListQuery(PaginationQuery, SortQuery):
    """稼働可否一覧クエリ"""
    worker_id: Optional[str] = None
    availability_date_from: Optional[date] = None
    availability_date_to: Optional[date] = None
    status: Optional[str] = None


class WorkerAvailabilityListItem(BaseModel):
    """稼働可否一覧の1行"""
    id: str
    worker_id: str
    worker_name: str
    availability_date: date
    status: str
    notes: Optional[str] = None
    updated_at: datetime


class WorkerAvailabilityListResponse(PageResponse[WorkerAvailabilityListItem]):
    """稼働可否一覧レスポンス"""
    pass


class WorkerAvailabilityUpsertRequest(BaseModel):
    """稼働可否更新リクエスト"""
    worker_id: Optional[str] = None
    availability_date: date
    status: str = Field(..., max_length=20)
    notes: Optional[str] = Field(None, max_length=2000)


class WorkerAvailabilityPreferenceResponse(BaseModel):
    """稼働者の基本スケジュール設定レスポンス"""
    worker_id: str
    weekly_default_statuses: dict[str, str] = Field(default_factory=dict)
    holiday_default_status: Optional[str] = None
    auto_apply_enabled: bool = True
    updated_at: Optional[datetime] = None


class WorkerAvailabilityPreferenceUpsertRequest(BaseModel):
    """稼働者の基本スケジュール設定更新リクエスト"""
    weekly_default_statuses: dict[str, str] = Field(default_factory=dict)
    holiday_default_status: Optional[str] = Field(None, max_length=20)
    auto_apply_enabled: bool = True


# ===========================
# Availability Calendar Schemas
# ===========================

class CalendarDayAssignment(BaseModel):
    """カレンダー1日内の配置情報"""
    id: str
    project_id: str
    project_name: str
    shift_slot_id: str
    shift_label: Optional[str] = None
    status: str
    role_name: str


class CalendarDayInfo(BaseModel):
    """カレンダー1日分の情報"""
    availability_status: Optional[str] = None
    availability_notes: Optional[str] = None
    assignments: list[CalendarDayAssignment] = Field(default_factory=list)


class CalendarWorkerRow(BaseModel):
    """カレンダービューの1稼働者行"""
    id: str
    name: str
    is_active: bool
    smoking_area_ok: Optional[bool] = None
    has_p_shirt: Optional[bool] = None
    has_best: Optional[bool] = None
    stores_training_done: Optional[bool] = None
    pioneer_training_done: Optional[bool] = None
    p_shirt_count: Optional[int] = None
    license_type: Optional[str] = None
    days: dict[str, CalendarDayInfo] = Field(default_factory=dict)


class AvailabilityCalendarResponse(BaseModel):
    """出勤可能日カレンダーレスポンス"""
    date_from: date
    date_to: date
    workers: list[CalendarWorkerRow]


# ===========================
# Expenses List Schemas
# ===========================

class ExpenseListQuery(PaginationQuery, SortQuery):
    """経費一覧クエリ"""
    project_id: Optional[str] = None
    worker_id: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    expense_date_from: Optional[date] = None
    expense_date_to: Optional[date] = None


class ExpenseListItem(BaseModel):
    """経費一覧の1行"""
    id: str
    expense_date: date
    project_id: str
    project_name: str
    worker_id: Optional[str] = None
    worker_name: str
    category: str
    amount: Decimal
    status: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    reject_reason: Optional[str] = None
    has_receipt: bool


class ExpenseListResponse(PageResponse[ExpenseListItem]):
    """経費一覧レスポンス"""
    pass


class ExpenseSubmissionResponse(BaseModel):
    """経費申請レスポンス"""
    id: str
    expense_date: date
    project_id: str
    project_name: str
    worker_id: Optional[str] = None
    worker_name: str
    category: str
    amount: Decimal
    description: Optional[str] = None
    status: str
    reject_reason: Optional[str] = None
    has_receipt: bool


class ExpenseActionRequest(BaseModel):
    """経費承認・却下リクエスト"""
    reject_reason: Optional[str] = Field(None, max_length=2000)


# ===========================
# Price Rules List Schemas
# ===========================

class PriceRuleListQuery(PaginationQuery, SortQuery):
    """単価ルール一覧クエリ"""
    is_active: Optional[bool] = None
    search: Optional[str] = Field(None, max_length=100)


class PriceRuleListItem(BaseModel):
    """単価ルール一覧の1行"""
    id: str
    name: str
    priority: int
    conditions: dict
    sales_price: Optional[Decimal] = None
    outsource_price: Optional[Decimal] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    is_active: bool
    notes: Optional[str] = None


class PriceRuleListResponse(PageResponse[PriceRuleListItem]):
    """単価ルール一覧レスポンス"""
    pass


class PriceRuleCreateRequest(BaseModel):
    """単価ルール作成リクエスト"""
    name: str = Field(..., min_length=1, max_length=200)
    priority: int = Field(100, ge=0, le=9999)
    conditions: dict
    sales_price: Optional[Decimal] = None
    outsource_price: Optional[Decimal] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    is_active: bool = True
    notes: Optional[str] = None


class PriceRuleUpdateRequest(PriceRuleCreateRequest):
    """単価ルール更新リクエスト"""
    pass


class PriceSalesListQuery(PaginationQuery, SortQuery):
    """売上単価一覧クエリ"""
    project_id: Optional[str] = None
    role_id: Optional[str] = None
    client_id: Optional[str] = None
    is_default: Optional[bool] = None


class PriceSalesListItem(BaseModel):
    """売上単価一覧の1行"""
    id: str
    project_id: Optional[str] = None
    project_name: str
    role_id: Optional[str] = None
    role_name: str
    client_id: Optional[str] = None
    client_name: str
    unit_price: Decimal
    unit_type: str
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    is_default: bool
    notes: Optional[str] = None


class PriceSalesListResponse(PageResponse[PriceSalesListItem]):
    """売上単価一覧レスポンス"""
    pass


class PriceSalesCreateRequest(BaseModel):
    """売上単価作成リクエスト"""
    project_id: Optional[str] = None
    role_id: Optional[str] = None
    client_id: Optional[str] = None
    unit_price: Decimal
    unit_type: Literal["hourly", "daily", "monthly", "fixed"]
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    is_default: bool = False
    notes: Optional[str] = None


class PriceSalesUpdateRequest(PriceSalesCreateRequest):
    """売上単価更新リクエスト"""
    pass


class PriceOutsourceListQuery(PaginationQuery, SortQuery):
    """外注単価一覧クエリ"""
    project_id: Optional[str] = None
    role_id: Optional[str] = None
    worker_id: Optional[str] = None
    is_default: Optional[bool] = None


class PriceOutsourceListItem(BaseModel):
    """外注単価一覧の1行"""
    id: str
    project_id: Optional[str] = None
    project_name: str
    worker_id: Optional[str] = None
    worker_name: str
    role_id: Optional[str] = None
    role_name: str
    unit_price: Decimal
    unit_type: str
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    is_default: bool
    notes: Optional[str] = None


class PriceOutsourceListResponse(PageResponse[PriceOutsourceListItem]):
    """外注単価一覧レスポンス"""
    pass


class PriceOutsourceCreateRequest(BaseModel):
    """外注単価作成リクエスト"""
    project_id: Optional[str] = None
    worker_id: Optional[str] = None
    role_id: Optional[str] = None
    unit_price: Decimal
    unit_type: Literal["hourly", "daily", "monthly", "fixed"]
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    is_default: bool = False
    notes: Optional[str] = None


class PriceOutsourceUpdateRequest(PriceOutsourceCreateRequest):
    """外注単価更新リクエスト"""
    pass


# ===========================
# Master Data List Schemas
# ===========================

class WorkerListQuery(PaginationQuery, SortQuery):
    """稼働者一覧クエリ"""
    search: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    supplier_id: Optional[str] = None


class WorkerListItem(BaseModel):
    """稼働者一覧の1行"""
    id: str
    name: str
    furigana: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    sole_proprietor_name: Optional[str] = None
    emergency_contact_name_kana: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    gender: Optional[str] = None
    invoice_registration_status: Optional[str] = None
    invoice_number: Optional[str] = None
    is_active: bool
    introducer_supplier_id: Optional[str] = None
    introducer_supplier_name: Optional[str] = None
    notes: Optional[str] = None
    # スタッフ資格・保有物
    smoking_area_ok: Optional[bool] = None
    has_p_shirt: Optional[bool] = None
    has_best: Optional[bool] = None
    stores_training_done: Optional[bool] = None
    pioneer_training_done: Optional[bool] = None
    p_shirt_count: Optional[int] = None
    license_type: Optional[str] = None


class WorkerListResponse(PageResponse[WorkerListItem]):
    """稼働者一覧レスポンス"""
    pass


class WorkerCreateRequest(BaseModel):
    """稼働者作成リクエスト"""
    name: str = Field(..., min_length=1, max_length=100)
    furigana: Optional[str] = Field(None, max_length=200)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    sole_proprietor_name: Optional[str] = Field(None, max_length=200)
    emergency_contact_name_kana: Optional[str] = Field(None, max_length=200)
    emergency_contact_phone: Optional[str] = Field(None, max_length=20)
    gender: Optional[str] = Field(None, max_length=20)
    invoice_registration_status: Optional[str] = Field(None, max_length=30)
    invoice_number: Optional[str] = Field(None, max_length=20)
    introducer_supplier_id: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True
    # スタッフ資格・保有物
    smoking_area_ok: Optional[bool] = None
    has_p_shirt: Optional[bool] = None
    has_best: Optional[bool] = None
    stores_training_done: Optional[bool] = None
    pioneer_training_done: Optional[bool] = None
    p_shirt_count: Optional[int] = None
    license_type: Optional[str] = None


class WorkerUpdateRequest(WorkerCreateRequest):
    """稼働者更新リクエスト"""
    pass


class WorkerQualsUpdateRequest(BaseModel):
    """稼働者資格のみ更新リクエスト（PATCH /api/workers/{id}/quals）"""
    smoking_area_ok: Optional[bool] = None
    p_shirt_count: Optional[int] = None
    has_best: Optional[bool] = None
    stores_training_done: Optional[bool] = None
    pioneer_training_done: Optional[bool] = None
    license_type: Optional[str] = None


class SupplierListQuery(PaginationQuery, SortQuery):
    """下請け一覧クエリ"""
    search: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class SupplierListItem(BaseModel):
    """下請け一覧の1行"""
    id: str
    name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    supplier_type: Optional[str] = None
    entity_type: Optional[str] = None
    payout_terms_days: int
    default_daily_price: Optional[Decimal] = None
    is_active: bool
    notes: Optional[str] = None


class SupplierListResponse(PageResponse[SupplierListItem]):
    """下請け一覧レスポンス"""
    pass


class SupplierCreateRequest(BaseModel):
    """下請け作成リクエスト"""
    name: str = Field(..., min_length=1, max_length=100)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=20)
    supplier_type: Optional[str] = Field(None, max_length=20)
    entity_type: Optional[str] = Field(None, max_length=20)
    payout_terms_days: int = Field(70, ge=0, le=365)
    default_daily_price: Optional[Decimal] = None
    is_active: bool = True
    notes: Optional[str] = None


class SupplierUpdateRequest(SupplierCreateRequest):
    """下請け更新リクエスト"""
    pass


class ClientListQuery(PaginationQuery, SortQuery):
    """クライアント一覧クエリ"""
    search: Optional[str] = Field(None, max_length=100)


class ClientListItem(BaseModel):
    """クライアント一覧の1行"""
    id: str
    name: str
    code: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    billing_email: Optional[str] = None


class ClientListResponse(PageResponse[ClientListItem]):
    """クライアント一覧レスポンス"""
    pass


class ClientCreateRequest(BaseModel):
    """クライアント作成リクエスト"""
    name: str = Field(..., min_length=1, max_length=200)
    code: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    contact_name: Optional[str] = Field(None, max_length=100)
    contact_email: Optional[str] = Field(None, max_length=255)
    billing_email: Optional[str] = Field(None, max_length=255)


class SiteListQuery(PaginationQuery, SortQuery):
    """現場一覧クエリ"""
    search: Optional[str] = Field(None, max_length=100)


class SiteListItem(BaseModel):
    """現場一覧の1行"""
    id: str
    name: str
    code: Optional[str] = None
    address: Optional[str] = None


class SiteListResponse(PageResponse[SiteListItem]):
    """現場一覧レスポンス"""
    pass


class SiteCreateRequest(BaseModel):
    """現場作成リクエスト"""
    name: str = Field(..., min_length=1, max_length=200)
    code: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None


class ProjectTypeListQuery(PaginationQuery, SortQuery):
    """案件種別一覧クエリ"""
    search: Optional[str] = Field(None, max_length=100)
    category_level: Optional[str] = None
    parent_id: Optional[str] = None
    selectable_only: bool = False


class ProjectTypeListItem(BaseModel):
    """案件種別一覧の1行"""
    id: str
    name: str
    code: Optional[str] = None
    category_level: str
    parent_id: Optional[str] = None
    description: Optional[str] = None


class ProjectTypeListResponse(PageResponse[ProjectTypeListItem]):
    """案件種別一覧レスポンス"""
    pass


class ProjectTypeCreateRequest(BaseModel):
    """案件種別作成リクエスト"""
    name: str = Field(..., min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    category_level: str = Field("minor", max_length=20)
    parent_id: Optional[str] = None
    description: Optional[str] = None


class ProjectTypeTreeItem(BaseModel):
    """案件種別ツリーの1ノード"""
    id: str
    name: str
    code: Optional[str] = None
    category_level: str
    parent_id: Optional[str] = None
    description: Optional[str] = None
    selectable: bool
    children: List["ProjectTypeTreeItem"] = Field(default_factory=list)


class ProjectTypeTreeResponse(BaseModel):
    """案件種別ツリーレスポンス"""
    items: List[ProjectTypeTreeItem]


class RegistrationRequestListQuery(PaginationQuery, SortQuery):
    """登録申請一覧クエリ"""
    request_type: Optional[str] = None
    status: Optional[str] = None
    source_type: Optional[str] = None
    search: Optional[str] = Field(None, max_length=100)


class RegistrationRequestFileItem(BaseModel):
    """登録申請添付ファイル"""
    id: str
    document_type: str
    document_part: str
    original_filename: str
    mime_type: str
    size_bytes: int
    scan_status: str
    uploaded_at: datetime
    delete_after: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class RegistrationFieldDifferenceItem(BaseModel):
    """重複候補との差分 1 項目"""
    field_name: str
    field_label: str
    request_value: Optional[str] = None
    existing_value: Optional[str] = None
    is_match: bool


class RegistrationDedupeCandidateItem(BaseModel):
    """重複候補"""
    target_type: str
    target_id: str
    display_name: str
    match_reasons: List[str] = Field(default_factory=list)
    phone: Optional[str] = None
    email: Optional[str] = None
    entity_type: Optional[str] = None
    notes: Optional[str] = None
    field_differences: List[RegistrationFieldDifferenceItem] = Field(default_factory=list)


class RegistrationRequestListItem(BaseModel):
    """登録申請一覧の1行"""
    id: str
    request_type: str
    status: str
    source_type: str
    summary_name: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    approved_target_type: Optional[str] = None
    approved_target_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    failed_attempts: int
    locked_at: Optional[datetime] = None
    dedupe_key: Optional[str] = None
    notes: Optional[str] = None


class RegistrationRequestListResponse(PageResponse[RegistrationRequestListItem]):
    """登録申請一覧レスポンス"""
    pass


class RegistrationRequestDetailResponse(BaseModel):
    """登録申請詳細レスポンス"""
    id: str
    request_type: str
    status: str
    source_type: str
    summary_name: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    reviewed_by_name: Optional[str] = None
    approved_target_type: Optional[str] = None
    approved_target_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    failed_attempts: int
    locked_at: Optional[datetime] = None
    dedupe_key: Optional[str] = None
    superseded_by_request_id: Optional[str] = None
    submitted_ip: Optional[str] = None
    user_agent: Optional[str] = None
    notes: Optional[str] = None
    detail_data: Optional[dict] = None
    dedupe_candidates: List[RegistrationDedupeCandidateItem] = Field(default_factory=list)
    files: List[RegistrationRequestFileItem] = Field(default_factory=list)


class RegistrationRequestApproveRequest(BaseModel):
    """登録申請承認リクエスト"""
    approved_target_id: Optional[str] = None
    dedupe_resolution: Optional[Literal["create_new", "merge_existing"]] = None
    notes: Optional[str] = None


class RegistrationRequestRejectRequest(BaseModel):
    """登録申請却下リクエスト"""
    reason: str = Field(..., min_length=1, max_length=500)
    notes: Optional[str] = None


class RegistrationLinkCreateRequest(BaseModel):
    """公開登録リンク作成リクエスト"""
    request_type: Literal["worker", "supplier_individual", "supplier_corporation", "introducer_identity"]
    expires_in_days: int = Field(7, ge=1, le=30)
    notes: Optional[str] = None


class RegistrationLinkResponse(BaseModel):
    """公開登録リンクレスポンス"""
    request_id: str
    request_type: str
    status: str
    expires_at: datetime
    public_form_url: str
    public_token: str
    access_pin: str
    failed_attempts: int
    locked_at: Optional[datetime] = None
    notes: Optional[str] = None


class PublicRegistrationAccessResponse(BaseModel):
    """公開登録フォームアクセス結果"""
    request_id: str
    request_type: str
    status: str
    expires_at: Optional[datetime] = None
    failed_attempts: int
    detail_data: Optional[dict] = None
    files: List[RegistrationRequestFileItem] = Field(default_factory=list)


class PublicRegistrationSubmitResponse(BaseModel):
    """公開登録フォーム送信結果"""
    request_id: str
    request_type: str
    status: str
    submitted_at: datetime
    dedupe_key: Optional[str] = None


class PublicRegistrationFileUploadResponse(BaseModel):
    """公開登録の添付ファイルアップロード結果"""
    file: RegistrationRequestFileItem
    files: List[RegistrationRequestFileItem] = Field(default_factory=list)


class PublicWorkerRegistrationSubmitRequest(BaseModel):
    token: str = Field(..., min_length=8, max_length=255)
    pin: str = Field(..., min_length=4, max_length=20)
    last_name: Optional[str] = Field(None, max_length=100)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name_furigana: Optional[str] = Field(None, max_length=100)
    first_name_furigana: Optional[str] = Field(None, max_length=100)
    sole_proprietor_name: Optional[str] = Field(None, max_length=200)
    gender: Optional[str] = Field(None, max_length=20)
    route_group: Optional[str] = Field(None, max_length=100)
    introducer_supplier_name_raw: Optional[str] = Field(None, max_length=200)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    zipcode: Optional[str] = Field(None, max_length=20)
    prefecture: Optional[str] = Field(None, max_length=50)
    city_address: Optional[str] = None
    building_address: Optional[str] = None
    emergency_contact_name_kana: Optional[str] = Field(None, max_length=200)
    emergency_contact_phone: Optional[str] = Field(None, max_length=20)
    bank_name: Optional[str] = Field(None, max_length=100)
    bank_branch: Optional[str] = Field(None, max_length=100)
    bank_branch_number: Optional[str] = Field(None, max_length=10)
    bank_account_type: Optional[str] = Field(None, max_length=20)
    bank_account_number: Optional[str] = Field(None, max_length=20)
    bank_account_holder: Optional[str] = Field(None, max_length=200)
    invoice_registration_status: Optional[str] = Field(None, max_length=30)
    invoice_registration_number: Optional[str] = Field(None, max_length=20)
    memo: Optional[str] = None


class PublicSupplierIndividualRegistrationSubmitRequest(BaseModel):
    token: str = Field(..., min_length=8, max_length=255)
    pin: str = Field(..., min_length=4, max_length=20)
    supplier_type: Optional[str] = Field(None, max_length=20)
    name: Optional[str] = Field(None, max_length=100)
    name_furigana: Optional[str] = Field(None, max_length=100)
    trade_name: Optional[str] = Field(None, max_length=200)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    zipcode: Optional[str] = Field(None, max_length=20)
    prefecture: Optional[str] = Field(None, max_length=50)
    city_address: Optional[str] = None
    building_address: Optional[str] = None
    bank_name: Optional[str] = Field(None, max_length=100)
    bank_branch: Optional[str] = Field(None, max_length=100)
    bank_branch_number: Optional[str] = Field(None, max_length=10)
    bank_account_type: Optional[str] = Field(None, max_length=20)
    bank_account_number: Optional[str] = Field(None, max_length=20)
    bank_account_holder_kana: Optional[str] = Field(None, max_length=200)
    invoice_registration_status: Optional[str] = Field(None, max_length=30)
    invoice_registration_number: Optional[str] = Field(None, max_length=20)
    memo: Optional[str] = None


class PublicSupplierCorporationRegistrationSubmitRequest(BaseModel):
    token: str = Field(..., min_length=8, max_length=255)
    pin: str = Field(..., min_length=4, max_length=20)
    supplier_type: Optional[str] = Field(None, max_length=20)
    company_name: Optional[str] = Field(None, max_length=200)
    company_name_furigana: Optional[str] = Field(None, max_length=200)
    representative_name: Optional[str] = Field(None, max_length=100)
    representative_name_furigana: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    zipcode: Optional[str] = Field(None, max_length=20)
    prefecture: Optional[str] = Field(None, max_length=50)
    city_address: Optional[str] = None
    building_address: Optional[str] = None
    bank_name: Optional[str] = Field(None, max_length=100)
    bank_branch: Optional[str] = Field(None, max_length=100)
    bank_branch_number: Optional[str] = Field(None, max_length=10)
    bank_account_type: Optional[str] = Field(None, max_length=20)
    bank_account_number: Optional[str] = Field(None, max_length=20)
    bank_account_holder_kana: Optional[str] = Field(None, max_length=200)
    invoice_registration_status: Optional[str] = Field(None, max_length=30)
    invoice_registration_number: Optional[str] = Field(None, max_length=20)
    memo: Optional[str] = None


class PublicIntroducerIdentityRegistrationSubmitRequest(BaseModel):
    token: str = Field(..., min_length=8, max_length=255)
    pin: str = Field(..., min_length=4, max_length=20)
    related_worker_request_id: Optional[str] = None
    related_supplier_request_id: Optional[str] = None
    subject_name: Optional[str] = Field(None, max_length=100)
    subject_name_furigana: Optional[str] = Field(None, max_length=100)
    submission_reason: Optional[str] = None
    memo: Optional[str] = None


class RoleListQuery(PaginationQuery, SortQuery):
    """役割一覧クエリ"""
    search: Optional[str] = Field(None, max_length=100)


class RoleListItem(BaseModel):
    """役割一覧の1行"""
    id: str
    name: str


# ===========================
# Staff Notice Schemas
# ===========================

class NoticeCreateRequest(BaseModel):
    """スタッフ通知作成リクエスト"""
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=4000)
    notice_type: str = Field("general", description="shift_confirm | project_change | general")
    priority: str = Field("normal", description="normal | urgent")
    target_type: str = Field("all", description="all | project | worker")
    target_project_id: Optional[str] = None
    target_worker_ids: Optional[List[str]] = None
    send_email: bool = Field(False, description="メール送信するか")
    push_action_type: Optional[str] = Field(None, description="none | ok_ng | confirm")


class NoticeListQuery(PaginationQuery, SortQuery):
    """通知一覧クエリ"""
    notice_type: Optional[str] = None
    target_type: Optional[str] = None


class NoticeListItem(BaseModel):
    """通知一覧の1行（管理者用）"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    notice_type: str
    priority: str
    target_type: str
    target_project_id: Optional[str] = None
    target_project_name: Optional[str] = None
    target_worker_ids: Optional[List[str]] = None
    send_email: bool
    push_action_type: Optional[str] = None
    sent_at: Optional[datetime] = None
    read_count: int = 0
    created_by: Optional[str] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    deleted_at: Optional[datetime] = None


class NoticeListResponse(BaseModel):
    """通知一覧レスポンス"""
    items: List[NoticeListItem]
    total: int
    offset: int
    limit: int


class WorkerNoticeItem(BaseModel):
    """スタッフ向け通知の1行"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    body: str
    notice_type: str
    priority: str
    target_project_id: Optional[str] = None
    target_project_name: Optional[str] = None
    push_action_type: Optional[str] = None
    is_read: bool = False
    read_at: Optional[datetime] = None
    # 返答状態: "ok" | "ng" | None(未回答)
    response: Optional[str] = None
    responded_at: Optional[datetime] = None
    created_at: datetime


class StaffNoticeRespondRequest(BaseModel):
    """スタッフ通知への返答リクエスト"""
    response: str  # "ok" | "ng"


class PushSubscriptionRequest(BaseModel):
    """Web Push サブスクリプション登録リクエスト"""
    endpoint: str
    p256dh: str
    auth: str
    user_agent_hash: Optional[str] = None


class VapidPublicKeyResponse(BaseModel):
    """VAPID 公開鍵レスポンス"""
    public_key: str


class WorkerNoticeListResponse(BaseModel):
    """スタッフ向け通知一覧レスポンス"""
    items: List[WorkerNoticeItem]
    unread_count: int
    total: int
    code: Optional[str] = None
    description: Optional[str] = None


class RoleListResponse(PageResponse[RoleListItem]):
    """役割一覧レスポンス"""
    pass


class RoleCreateRequest(BaseModel):
    """役割作成リクエスト"""
    name: str = Field(..., min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None


# ===========================
# Invoice Schemas
# ===========================

class InvoiceListQuery(PaginationQuery, SortQuery):
    """請求一覧クエリ"""
    period_key: Optional[str] = Field(None, pattern=r"^\d{6}$")
    client_id: Optional[str] = None
    project_id: Optional[str] = None
    status: Optional[str] = None
    version: Optional[int] = Field(None, ge=1)


class InvoiceListItem(BaseModel):
    """請求一覧の1行"""
    id: str
    invoice_number: str
    client_id: str
    client_name: str
    project_id: Optional[str] = None
    project_name: str
    period_key: str
    billing_date: date
    document_type: str
    subject: Optional[str] = None
    addressee_company_name: Optional[str] = None
    addressee_name: Optional[str] = None
    fixed_office_fee_amount: Optional[Decimal] = None
    version: int
    status: str
    total_amount: Decimal
    issued_at: Optional[datetime] = None
    has_pdf: bool
    pdf_storage_key: Optional[str] = None


class InvoiceListResponse(PageResponse[InvoiceListItem]):
    """請求一覧レスポンス"""
    pass

class InvoiceGenerateRequest(BaseModel):
    """請求書生成リクエスト"""
    project_id: str
    period_key: str = Field(..., pattern=r"^\d{6}$", description="期間キー YYYYMM")
    document_type: Literal["invoice", "estimate"] = "invoice"
    client_staff_id: Optional[str] = None
    subject: Optional[str] = Field(None, max_length=255)
    fixed_office_fee_amount: Optional[Decimal] = Field(None, ge=0)
    billing_date: Optional[date] = None


class InvoiceLineResponse(BaseModel):
    """請求書明細行"""
    line_type: str
    description: str
    quantity: Optional[Decimal]
    unit_price: Optional[Decimal]
    amount: Decimal


class InvoiceResponse(BaseModel):
    """請求書レスポンス"""
    id: str
    invoice_number: str
    document_type: str
    client_name: str
    project_name: str
    period_key: str
    billing_date: date
    subject: Optional[str] = None
    addressee_company_name: Optional[str] = None
    addressee_name: Optional[str] = None
    addressee_email: Optional[str] = None
    addressee_address: Optional[str] = None
    fixed_office_fee_amount: Optional[Decimal] = None
    total_amount: Decimal
    status: str
    lines: List[InvoiceLineResponse]
    issued_at: Optional[datetime]


# ===========================
# Payout Schemas
# ===========================

class PayoutListQuery(PaginationQuery, SortQuery):
    """支払一覧クエリ"""
    period_key: Optional[str] = Field(None, pattern=r"^\d{6}$")
    worker_id: Optional[str] = None
    supplier_id: Optional[str] = None
    recipient_type: Optional[str] = None
    recipient_id: Optional[str] = None
    project_id: Optional[str] = None
    status: Optional[str] = None
    missing_default_recipient_only: bool = False
    delivery_state: Optional[Literal["unsent", "failed"]] = None


class PayoutListItem(BaseModel):
    """支払一覧の1行"""
    id: str
    payout_number: str
    payee_name: str
    payee_type: str
    recipient_type: Optional[str] = None
    recipient_id: Optional[str] = None
    payee_name_snapshot: Optional[str] = None
    project_id: Optional[str] = None
    project_name: str
    period_key: str
    version: int
    status: str
    total_amount: Decimal
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    has_pdf: bool = False
    pdf_storage_key: Optional[str] = None
    default_recipient_email: Optional[str] = None
    last_delivery_status: Optional[str] = None
    last_delivered_at: Optional[datetime] = None
    last_delivery_recipient: Optional[str] = None


class PayoutListResponse(PageResponse[PayoutListItem]):
    """支払一覧レスポンス"""
    pass

class PayoutGenerateRequest(BaseModel):
    """支払明細生成リクエスト"""
    project_id: Optional[str] = None
    worker_id: Optional[str] = None
    recipient_type: Optional[str] = Field(None, max_length=20)
    recipient_id: Optional[str] = None
    support_fee_amount: Optional[Decimal] = Field(None, ge=0)
    period_key: str = Field(..., pattern=r"^\d{6}$", description="期間キー YYYYMM")


class PayoutLineResponse(BaseModel):
    """支払明細行"""
    line_type: str
    description: str
    quantity: Optional[Decimal]
    unit_price: Optional[Decimal]
    amount: Decimal


class PayoutResponse(BaseModel):
    """支払明細レスポンス"""
    id: str
    payout_number: str
    worker_name: str
    payee_name: str
    recipient_type: Optional[str] = None
    recipient_id: Optional[str] = None
    project_name: str
    period_key: str
    total_amount: Decimal
    status: str
    lines: List[PayoutLineResponse]
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None


class PayoutDeliveryRequest(BaseModel):
    """支払明細送信リクエスト"""
    recipient_email: Optional[str] = None
    delivery_note: Optional[str] = Field(None, max_length=500)
    internal_note: Optional[str] = Field(None, max_length=500)


class PayoutDeliveryItem(BaseModel):
    """支払明細送信記録"""
    id: str
    payout_id: str
    recipient_email: str
    status: str
    provider: Optional[str] = None
    delivered_by: Optional[str] = None
    pdf_storage_key: Optional[str] = None
    delivery_note: Optional[str] = None
    internal_note: Optional[str] = None
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime


class PayoutDeliveryListResponse(BaseModel):
    """支払明細送信履歴レスポンス"""
    items: List[PayoutDeliveryItem]


class MonthlyBillingGenerateRequest(BaseModel):
    """月次一括 請求/支払 生成リクエスト"""
    period_key: str = Field(..., pattern=r"^\d{6}$", description="期間キー YYYYMM")


class MonthlyBillingGenerateResponse(BaseModel):
    """月次一括 請求/支払 生成レスポンス"""
    period_key: str
    generated_invoices: int
    skipped_invoices: int
    failed_invoices: List[dict]
    generated_payouts: int
    skipped_payouts: int
    failed_payouts: List[dict]


# ===========================
# Closing Schemas
# ===========================

class SoftCloseRequest(BaseModel):
    """Soft Close リクエスト"""
    project_id: str
    period_key: str = Field(..., pattern=r"^\d{6}$")
    actor: Optional[str] = Field(None, description="実行者")
    reason: Optional[str] = Field(None, description="締め理由")


class HardCloseRequest(BaseModel):
    """Hard Close リクエスト"""
    project_id: str
    period_key: str = Field(..., pattern=r"^\d{6}$")
    actor: Optional[str] = Field(None, description="実行者")
    approver: str = Field(..., description="承認者")
    reason: Optional[str] = Field(None, description="締め理由")


class SoftCloseReleaseRequest(BaseModel):
    """Soft Close 解除リクエスト"""
    project_id: str
    period_key: str = Field(..., pattern=r"^\d{6}$")
    actor: Optional[str] = Field(None, description="実行者")
    approver: str = Field(..., description="承認者")
    reason: str = Field(..., min_length=1, description="解除理由")


class HardCloseReleaseRequest(BaseModel):
    """Hard Close 解除リクエスト"""
    project_id: str
    period_key: str = Field(..., pattern=r"^\d{6}$")
    actor: Optional[str] = Field(None, description="実行者")
    approver: str = Field(..., description="承認者")
    reason: str = Field(..., min_length=1, description="解除理由")


class ClosingResponse(BaseModel):
    """締め処理レスポンス"""
    id: str
    project_id: str
    period_key: str
    status: str
    closed_at: Optional[datetime]
    closed_by: Optional[str]
    release_count: int
    last_released_at: Optional[datetime] = None
    last_released_by: Optional[str] = None
    last_release_reason: Optional[str] = None
    reclose_deadline: Optional[datetime] = None


# ===========================
# Audit Log Schemas
# ===========================

class AuditLogSearchRequest(PaginationQuery):
    """監査ログ検索リクエスト"""
    period_key: Optional[str] = Field(None, pattern=r"^\d{6}$")
    project_id: Optional[str] = None
    action_type: Optional[str] = None
    action_group: Optional[str] = None
    actor: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class AuditLogResponse(BaseModel):
    """監査ログレスポンス"""
    id: str
    timestamp: datetime
    action: str
    actor: Optional[str] = None
    actor_role: Optional[str] = None
    project_id: Optional[str] = None
    target_type: Optional[str]
    target_id: Optional[str]
    reason: Optional[str] = None
    details: Optional[dict]
    details_summary: Optional[str] = None


class AuditLogListResponse(PageResponse[AuditLogResponse]):
    """監査ログ一覧レスポンス"""
    pass


# ===========================
# VanzaiStaff Schemas
# ===========================

class VanzaiStaffListQuery(PaginationQuery, SortQuery):
    """VANZAI担当者一覧クエリ"""
    search: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class VanzaiStaffItem(BaseModel):
    """VANZAI担当者の1行"""
    id: str
    name: str
    role: Optional[str] = None
    linked_worker_id: Optional[str] = None
    linked_worker_name: Optional[str] = None
    playing_manager_fee_type: Optional[Literal["subordinate_man_days", "fixed_amount"]] = None
    playing_manager_fixed_fee: Optional[Decimal] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: bool
    notes: Optional[str] = None


class VanzaiStaffListResponse(PageResponse[VanzaiStaffItem]):
    """VANZAI担当者一覧レスポンス"""
    pass


class VanzaiStaffCreateRequest(BaseModel):
    """VANZAI担当者作成リクエスト"""
    name: str = Field(..., min_length=1, max_length=100)
    role: Optional[str] = Field(None, max_length=100)
    linked_worker_id: Optional[str] = None
    playing_manager_fee_type: Optional[Literal["subordinate_man_days", "fixed_amount"]] = None
    playing_manager_fixed_fee: Optional[Decimal] = Field(None, ge=0)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    is_active: bool = True
    notes: Optional[str] = None


class VanzaiStaffUpdateRequest(VanzaiStaffCreateRequest):
    """VANZAI担当者更新リクエスト"""
    pass


# ===========================
# ClientStaff Schemas
# ===========================

class ClientStaffListQuery(PaginationQuery, SortQuery):
    """クライアント担当者一覧クエリ"""
    client_id: Optional[str] = None
    is_active: Optional[bool] = None


class ClientStaffItem(BaseModel):
    """クライアント担当者の1行"""
    id: str
    client_id: str
    name: str
    role: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: bool
    notes: Optional[str] = None


class ClientStaffListResponse(PageResponse[ClientStaffItem]):
    """クライアント担当者一覧レスポンス"""
    pass


class ClientStaffCreateRequest(BaseModel):
    """クライアント担当者作成リクエスト"""
    name: str = Field(..., min_length=1, max_length=100)
    role: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    is_active: bool = True
    notes: Optional[str] = None


class ClientStaffUpdateRequest(ClientStaffCreateRequest):
    """クライアント担当者更新リクエスト"""
    pass


# ===========================
# WorkerBankAccount Schemas
# ===========================

class WorkerBankAccountItem(BaseModel):
    """稼働者口座の1行"""
    id: str
    worker_id: str
    bank_name: str
    branch_name: str
    branch_code: Optional[str] = None
    account_type: str
    account_number: str
    account_holder_kana: str
    transfer_destination_name: Optional[str] = None
    effective_from: date
    effective_until: Optional[date] = None
    is_primary: bool


class WorkerBankAccountListResponse(BaseModel):
    """稼働者口座一覧レスポンス"""
    items: List[WorkerBankAccountItem]
    total: int


class WorkerBankAccountCreateRequest(BaseModel):
    """稼働者口座作成リクエスト"""
    bank_name: str = Field(..., min_length=1, max_length=100)
    branch_name: str = Field(..., min_length=1, max_length=100)
    branch_code: Optional[str] = Field(None, max_length=10)
    account_type: str = Field(..., max_length=20)
    account_number: str = Field(..., min_length=1, max_length=20)
    account_holder_kana: str = Field(..., min_length=1, max_length=200)
    transfer_destination_name: Optional[str] = Field(None, max_length=200)
    effective_from: date
    effective_until: Optional[date] = None
    is_primary: bool = False


class WorkerBankAccountUpdateRequest(WorkerBankAccountCreateRequest):
    """稼働者口座更新リクエスト"""
    pass


# ===========================
# SupplierBankAccount Schemas
# ===========================

class SupplierBankAccountItem(BaseModel):
    """下請け口座の1行"""
    id: str
    supplier_id: str
    bank_name: str
    branch_name: str
    branch_code: Optional[str] = None
    account_type: str
    account_number: str
    account_holder_kana: str
    transfer_destination_name: Optional[str] = None
    effective_from: date
    effective_until: Optional[date] = None
    is_primary: bool


class SupplierBankAccountListResponse(BaseModel):
    """下請け口座一覧レスポンス"""
    items: List[SupplierBankAccountItem]
    total: int


class SupplierBankAccountCreateRequest(BaseModel):
    """下請け口座作成リクエスト"""
    bank_name: str = Field(..., min_length=1, max_length=100)
    branch_name: str = Field(..., min_length=1, max_length=100)
    branch_code: Optional[str] = Field(None, max_length=10)
    account_type: str = Field(..., max_length=20)
    account_number: str = Field(..., min_length=1, max_length=20)
    account_holder_kana: str = Field(..., min_length=1, max_length=200)
    transfer_destination_name: Optional[str] = Field(None, max_length=200)
    effective_from: date
    effective_until: Optional[date] = None
    is_primary: bool = False


class SupplierBankAccountUpdateRequest(SupplierBankAccountCreateRequest):
    """下請け口座更新リクエスト"""
    pass


# ===========================
# OCR Receipt Schemas
# ===========================

class OcrSourceImageItem(BaseModel):
    id: str
    source_type: str
    original_filename: Optional[str] = None
    sha256: str
    mime_type: Optional[str] = None
    size_bytes: int
    period_key: Optional[str] = None
    parse_status: str
    uploaded_by: Optional[str] = None
    last_job_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    reused_existing: bool = False
    has_filename_duplicate: bool = False


class OcrSourceImageListResponse(BaseModel):
    items: List["OcrSourceImageItem"]
    total: int


class OcrSourceImageDeleteRequest(BaseModel):
    image_ids: List[str] = Field(..., min_length=1)


class OcrSourceImageDeleteResponse(BaseModel):
    deleted_count: int


class OcrSourceImageUpdateRequest(BaseModel):
    original_filename: str = Field(..., min_length=1, max_length=255)


class OcrParseJobRequest(BaseModel):
    image_ids: List[str] = Field(..., min_length=1)


class OcrParseJobResponse(BaseModel):
    id: str
    status: str
    image_count: int
    success_count: int
    failed_count: int
    row_count: int
    executed_by: Optional[str] = None
    completed_at: Optional[datetime] = None


class OcrExtractedRowItem(BaseModel):
    id: str
    source_image_id: str
    source_image_filename: Optional[str] = None
    parse_job_id: Optional[str] = None
    source_type: str
    period_key: Optional[str] = None
    record_date: Optional[date] = None
    record_time: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: str
    transaction_no: Optional[str] = None
    receipt_no: Optional[str] = None
    payment_method: Optional[str] = None
    terminal_id: Optional[str] = None
    cash_sales: Optional[Decimal] = None
    credit_sales: Optional[Decimal] = None
    transaction_count: Optional[int] = None
    tax_included: Optional[Decimal] = None
    subtotal: Optional[Decimal] = None
    store_name: Optional[str] = None
    confidence: Optional[Decimal] = None
    amount_inferred: bool = False
    amount_source: Optional[str] = None
    datetime_source: Optional[str] = None
    confirm_required: bool = True
    manually_edited: bool = False
    status: str
    validation_errors: Optional[List[str]] = None
    project_id: Optional[str] = None
    report_date: Optional[date] = None
    linked_entity_type: Optional[str] = None
    linked_entity_id: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    confirmed_by: Optional[str] = None
    # --- paygate_settlement 専用項目（計画書 v4） ---
    terminal_short_id: Optional[str] = None
    pos_sales: Optional[Decimal] = None
    other_payment: Optional[Decimal] = None
    cash_unit_count: Optional[int] = None
    pos_unit_count: Optional[int] = None
    work_date: Optional[date] = None
    unit_breakdown_status: Optional[str] = None
    unit_breakdown_json: Optional[dict] = None
    amount_ones_digit_ok: Optional[bool] = None
    blocking_errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    duplicate_receipt_candidate: bool = False
    reconciliation_eligible: bool = True
    excluded_reason: Optional[str] = None
    voided_at: Optional[datetime] = None
    voided_by: Optional[str] = None
    void_reason: Optional[str] = None
    branch_id: Optional[str] = None
    staff_id: Optional[str] = None


class OcrExtractedRowListResponse(BaseModel):
    items: List[OcrExtractedRowItem]
    total: int


class OcrExtractedRowUpdateRequest(BaseModel):
    record_date: Optional[date] = None
    record_time: Optional[str] = None
    amount: Optional[Decimal] = None
    transaction_no: Optional[str] = None
    receipt_no: Optional[str] = None
    payment_method: Optional[str] = None
    terminal_id: Optional[str] = None
    cash_sales: Optional[Decimal] = None
    credit_sales: Optional[Decimal] = None
    transaction_count: Optional[int] = None
    tax_included: Optional[Decimal] = None
    subtotal: Optional[Decimal] = None
    store_name: Optional[str] = None
    status: Optional[str] = None
    project_id: Optional[str] = None
    report_date: Optional[date] = None
    # --- paygate_settlement 専用項目 ---
    terminal_short_id: Optional[str] = None
    pos_sales: Optional[Decimal] = None
    other_payment: Optional[Decimal] = None
    branch_id: Optional[str] = None
    staff_id: Optional[str] = None


class OcrRowVoidRequest(BaseModel):
    void_reason: str = Field(..., min_length=1, max_length=500)


class OcrRowReconciliationEligibilityRequest(BaseModel):
    eligible: bool
    excluded_reason: Optional[str] = Field(None, max_length=200)


class OcrRowsConfirmRequest(BaseModel):
    row_ids: List[str] = Field(..., min_length=1)


class OcrRowsConfirmResponse(BaseModel):
    confirmed_count: int


class OcrRowsConfirmRejectedResponse(BaseModel):
    detail: str = "Some rows cannot be confirmed"
    rejected_row_ids: List[str]
    reasons: dict[str, List[str]]


class OcrRowsDeleteRequest(BaseModel):
    row_ids: List[str] = Field(..., min_length=1)


class OcrRowsDeleteResponse(BaseModel):
    deleted_count: int


class OcrMonthlySummaryItem(BaseModel):
    period_key: str
    source_type: str
    row_count: int
    total_amount: str


class OcrMonthlySummaryResponse(BaseModel):
    items: List[OcrMonthlySummaryItem]


class OcrReconciliationColumnMapping(BaseModel):
    transaction_no: Optional[str] = None
    receipt_no: Optional[str] = None
    record_date: Optional[str] = None
    amount: Optional[str] = None


class OcrReconciliationResultItem(BaseModel):
    id: str
    match_status: str
    ocr_row_id: Optional[str] = None
    hq_row_index: Optional[int] = None
    hq_payload: Optional[dict] = None
    amount_diff: Optional[Decimal] = None
    notes: Optional[str] = None


class OcrReconciliationBatchResponse(BaseModel):
    id: str
    period_key: Optional[str] = None
    file_name: str
    row_count: int
    matched_count: int
    unmatched_ocr_count: int
    unmatched_hq_count: int
    amount_diff_count: int
    results: List[OcrReconciliationResultItem]


class OcrRowLinkRequest(BaseModel):
    linked_entity_type: str
    linked_entity_id: str
    project_id: Optional[str] = None


class OcrSelfReportCompareResponse(BaseModel):
    period_key: str
    project_id: Optional[str] = None
    ocr_row_count: int
    ocr_total_amount: str
    linked_count: int
    self_report_available: bool
    message: str


# ===========================
# Inventory Reconciliation Schemas (計画書 v4 Phase 2)
# ===========================

class InventorySnapshotItem(BaseModel):
    id: str
    branch_id: str
    terminal_short_id: str
    work_date: date
    staff_id: Optional[str] = None
    opening_count: int
    closing_count: int
    adjustment_count: int = 0
    adjustment_reason: Optional[str] = None
    inventory_decrease: int
    entered_by: str
    entered_at: datetime
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class InventorySnapshotListResponse(BaseModel):
    items: List[InventorySnapshotItem]
    total: int


class InventorySnapshotCreateRequest(BaseModel):
    branch_id: str = Field(..., min_length=1, max_length=50)
    terminal_short_id: str = Field(..., min_length=1, max_length=20)
    work_date: date
    staff_id: Optional[str] = Field(None, max_length=50)
    opening_count: int = Field(..., ge=0)
    closing_count: int = Field(..., ge=0)
    adjustment_count: int = 0
    adjustment_reason: Optional[str] = None
    note: Optional[str] = None


class InventorySnapshotUpdateRequest(BaseModel):
    staff_id: Optional[str] = Field(None, max_length=50)
    opening_count: Optional[int] = Field(None, ge=0)
    closing_count: Optional[int] = Field(None, ge=0)
    adjustment_count: Optional[int] = None
    adjustment_reason: Optional[str] = None
    note: Optional[str] = None


class InventoryReconciliationRunRequest(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    period_key: Optional[str] = None


class InventoryReconciliationResultItem(BaseModel):
    id: str
    batch_id: str
    branch_id: str
    terminal_short_id: str
    work_date: date
    ocr_row_id: Optional[str] = None
    inventory_snapshot_id: Optional[str] = None
    ocr_transaction_count: Optional[int] = None
    inventory_decrease: Optional[int] = None
    diff: Optional[int] = None
    match_status: str
    diff_reason_category: Optional[str] = None
    notes: Optional[str] = None


class InventoryReconciliationResultUpdateRequest(BaseModel):
    diff_reason_category: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    match_status: Optional[str] = None


class InventoryReconciliationBatchResponse(BaseModel):
    id: str
    period_key: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    executed_by: Optional[str] = None
    total_count: int
    matched_count: int
    adjusted_matched_count: int
    count_mismatch_count: int
    sales_only_count: int
    inventory_only_count: int
    excluded_count: int
    results: List[InventoryReconciliationResultItem] = []


class InventoryReconciliationBatchListResponse(BaseModel):
    items: List[InventoryReconciliationBatchResponse]
    total: int


# ===========================
# Error Response
# ===========================

class ErrorResponse(BaseModel):
    """エラーレスポンス"""
    model_config = ConfigDict(populate_by_name=True)

    error_code: str
    message: str
    detail: Optional[dict] = Field(
        default=None,
        validation_alias=AliasChoices("detail", "details"),
        serialization_alias="detail",
    )
