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
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    introducer_supplier_id: Optional[str] = None
    introducer_supplier_name: Optional[str] = None
    notes: Optional[str] = None


class WorkerListResponse(PageResponse[WorkerListItem]):
    """稼働者一覧レスポンス"""
    pass


class WorkerCreateRequest(BaseModel):
    """稼働者作成リクエスト"""
    name: str = Field(..., min_length=1, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    introducer_supplier_id: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True


class WorkerUpdateRequest(WorkerCreateRequest):
    """稼働者更新リクエスト"""
    pass


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


class ProjectTypeListItem(BaseModel):
    """案件種別一覧の1行"""
    id: str
    name: str
    code: Optional[str] = None
    description: Optional[str] = None


class ProjectTypeListResponse(PageResponse[ProjectTypeListItem]):
    """案件種別一覧レスポンス"""
    pass


class ProjectTypeCreateRequest(BaseModel):
    """案件種別作成リクエスト"""
    name: str = Field(..., min_length=1, max_length=100)
    code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None


class RoleListQuery(PaginationQuery, SortQuery):
    """役割一覧クエリ"""
    search: Optional[str] = Field(None, max_length=100)


class RoleListItem(BaseModel):
    """役割一覧の1行"""
    id: str
    name: str
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
    client_name: str
    project_name: str
    period_key: str
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
    project_id: str
    worker_id: str
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
