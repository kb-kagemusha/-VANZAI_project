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
    role_id: str
    role_name: str
    status: str
    cancel_reason: Optional[str] = None
    locked_price_sales: Optional[Decimal] = None
    locked_price_outsource: Optional[Decimal] = None


class AssignmentListResponse(PageResponse[AssignmentListItem]):
    """アサイン一覧レスポンス"""
    pass


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
    client_name: str
    site_name: str
    project_type_name: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: bool


class ProjectListResponse(PageResponse[ProjectListItem]):
    """案件一覧レスポンス"""
    pass


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
    has_receipt: bool


class ExpenseListResponse(PageResponse[ExpenseListItem]):
    """経費一覧レスポンス"""
    pass


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
    sales_price: Optional[Decimal] = None
    outsource_price: Optional[Decimal] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    is_active: bool


class PriceRuleListResponse(PageResponse[PriceRuleListItem]):
    """単価ルール一覧レスポンス"""
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


class PriceSalesListResponse(PageResponse[PriceSalesListItem]):
    """売上単価一覧レスポンス"""
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


class PriceOutsourceListResponse(PageResponse[PriceOutsourceListItem]):
    """外注単価一覧レスポンス"""
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


class WorkerListResponse(PageResponse[WorkerListItem]):
    """稼働者一覧レスポンス"""
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
    payout_terms_days: int
    default_daily_price: Optional[Decimal] = None
    is_active: bool


class SupplierListResponse(PageResponse[SupplierListItem]):
    """下請け一覧レスポンス"""
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
