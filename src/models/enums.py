"""
Enums for transaction models
仕様参照: DESIGN_SPEC_v0.3 セクション6.2, 6.3
"""
from enum import Enum


class AssignmentStatus(str, Enum):
    """
    アサインステータス
    仕様参照: 6.2 assignment.status
    """
    TENTATIVE = "tentative"  # 仮確定
    CONFIRMED = "confirmed"  # 確定
    CANCELED = "canceled"    # キャンセル


class AssignmentWorkerResponseStatus(str, Enum):
    """稼働者による予定確認応答ステータス"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class ActualStatus(str, Enum):
    """
    実績ステータス
    仕様参照: 6.2 actual.status
    
    不変条件（6.3）: 集計対象は status=active のみ
    """
    ACTIVE = "active"          # 有効（集計対象）
    INVALID = "invalid"        # 無効化（キャンセル等）
    SUPERSEDED = "superseded"  # 置換済み（洗い替え）


class ImportMode(str, Enum):
    """
    CSV取り込みモード
    仕様参照: 9.4 import_batch.mode
    """
    APPEND = "append"                        # 常に新規追加（検証用）
    UPSERT_BY_EXTERNAL_KEY = "upsert_by_external_key"  # 外部キーで上書き
    REPLACE_SCOPE = "replace_scope"          # 範囲洗い替え（推奨）


class ImportScopeType(str, Enum):
    """
    洗い替えスコープ種別
    仕様参照: 9.5 replace_scope のスコープ定義
    """
    PROJECT_MONTH = "project_month"         # 案件×月（推奨）
    PROJECT_DAY = "project_day"             # 案件×日
    PROJECT_DAY_WORKER = "project_day_worker"  # 案件×日×稼働者


class ImportBatchStatus(str, Enum):
    """
    取り込みバッチステータス
    """
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL_ERROR = "partial_error"
    FAILED = "failed"


class RoundingMethod(str, Enum):
    """
    時間丸めメソッド
    仕様参照: 8.1 rounding_method
    """
    FLOOR = "floor"    # 切り捨て
    CEIL = "ceil"      # 切り上げ
    NEAREST = "nearest"  # 四捨五入


class BreakDeductionRule(str, Enum):
    """
    休憩控除ルール
    仕様参照: 8.1 break_deduction_rule
    """
    AUTO = "auto"      # 自動（break_minutes採用、空なら0で警告）
    MANUAL = "manual"  # 手動（空ならエラー）
    NONE = "none"      # 控除なし


class TimeCalcMode(str, Enum):
    """
    時間計算モード
    仕様参照: 8.1 time_calc_mode
    """
    SYSTEM_FIRST = "system_first"      # システム計算優先
    CSV_HOURS_FIRST = "csv_hours_first"  # CSVのhours優先


class NightCalcMode(str, Enum):
    """
    深夜計算モード
    仕様参照: 8.1 night_calc_mode
    """
    STORE_MINUTES = "store_minutes"  # 深夜時間を保存
    DYNAMIC = "dynamic"              # 動的計算


class LineType(str, Enum):
    """
    請求書・支払明細の明細行種別
    仕様参照: 17.3, 18.4
    """
    WORK = "actual"            # 稼働実績
    EXPENSE = "expense"        # 経費
    INCENTIVE = "incentive"    # インセンティブ


class AuditAction(str, Enum):
    """
    監査ログアクション種別
    仕様参照: 16章
    """
    # CSV取り込み関連
    IMPORT_BATCH_CREATED = "import_batch_created"
    IMPORT_BATCH_COMPLETED = "import_batch_completed"
    REPLACE_SCOPE_EXECUTED = "replace_scope_executed"
    ACTUAL_SUPERSEDED = "actual_superseded"
    ACTUAL_INVALIDATED = "actual_invalidated"
    ATTENDANCE_CHECKED_IN = "attendance_checked_in"
    ATTENDANCE_CHECKED_OUT = "attendance_checked_out"
    AVAILABILITY_UPDATED = "availability_updated"
    STAFF_AVAILABILITY_PREFERENCES_UPDATED = "staff_availability_preferences_updated"
    
    # アサイン関連
    ASSIGNMENT_CANCELED = "assignment_canceled"
    ASSIGNMENT_STATUS_CHANGED = "assignment_status_changed"
    ASSIGNMENT_WORKER_RESPONSE_UPDATED = "assignment_worker_response_updated"
    ASSIGNMENT_RESPONSE_REMINDER_SENT = "assignment_response_reminder_sent"
    ASSIGNMENT_RESPONSE_REMINDER_FAILED = "assignment_response_reminder_failed"
    ASSIGNMENT_RESPONSE_ESCALATION_SENT = "assignment_response_escalation_sent"
    ASSIGNMENT_RESPONSE_ESCALATION_FAILED = "assignment_response_escalation_failed"
    ASSIGNMENT_SELECTION_SET_SAVED = "assignment_selection_set_saved"
    ASSIGNMENT_SELECTION_SET_DELETED = "assignment_selection_set_deleted"
    
    # 単価関連
    PRICE_RULE_CHANGED = "price_rule_changed"
    PRICE_RESOLVED = "price_resolved"
    
    # 締め関連
    CLOSING_SOFT_CLOSED = "closing_soft_closed"
    CLOSING_SOFT_RELEASED = "closing_soft_released"
    CLOSING_HARD_CLOSED = "closing_hard_closed"
    CLOSING_HARD_RELEASED = "closing_hard_released"
    
    # 請求・支払関連
    INVOICE_CREATED = "invoice_created"
    INVOICE_ISSUED = "invoice_issued"
    INVOICE_CORRECTED = "invoice_corrected"
    INVOICE_REISSUED = "invoice_reissued"
    PAYOUT_CREATED = "payout_created"
    PAYOUT_APPROVED = "payout_approved"
    PAYOUT_PAID = "payout_paid"
    PAYOUT_CORRECTED = "payout_corrected"
    PAYOUT_DELIVERY_SENT = "payout_delivery_sent"
    PAYOUT_DELIVERY_FAILED = "payout_delivery_failed"
    EXPENSE_SUBMITTED = "expense_submitted"
    EXPENSE_APPROVED = "expense_approved"
    EXPENSE_REJECTED = "expense_rejected"

    # スタッフ通知関連
    NOTICE_CREATED = "notice_created"
    NOTICE_SENT = "notice_sent"
    NOTICE_DELETED = "notice_deleted"


class InvoiceStatus(str, Enum):
    """
    請求書ステータス
    仕様参照: 6.2, 11.1
    """
    PREPARING = "preparing"  # 準備中
    ISSUED = "issued"        # 発行済み
    CLOSED = "closed"        # 締め（Hard Close）


class PayoutStatus(str, Enum):
    """
    支払明細ステータス
    仕様参照: 6.2, 11.1
    """
    PREPARING = "preparing"  # 準備中
    APPROVED = "approved"    # 承認済み
    PAID = "paid"            # 支払済み
    CLOSED = "closed"        # 締め（Hard Close）


class UserRole(str, Enum):
    """
    ユーザーロール
    仕様参照: 5.1 ロールと権限
    """
    ADMIN = "admin"              # マスタ編集、単価ルール変更、締め、内部締め解除
    OPS = "ops"                  # 案件/シフト/アサイン作成、実績取り込み、請求/支払の生成
    ACCOUNTING = "accounting"    # 請求発行、支払承認、締め（Hard Close）承認
    SITE_MANAGER = "site_manager"  # 担当案件の参照、CSV提出、エラー修正再提出
    WORKER = "worker"            # 参照のみ


class Permission(str, Enum):
    """
    権限種別
    仕様参照: 5.1, 5.2
    """
    # マスタデータ
    MASTER_READ = "master_read"
    MASTER_WRITE = "master_write"
    
    # 単価
    PRICE_READ = "price_read"
    PRICE_WRITE = "price_write"
    
    # 案件
    PROJECT_READ = "project_read"
    PROJECT_WRITE = "project_write"
    
    # シフト・アサイン
    SHIFT_READ = "shift_read"
    SHIFT_WRITE = "shift_write"
    ASSIGNMENT_READ = "assignment_read"
    ASSIGNMENT_RESPONSE = "assignment_response"
    ASSIGNMENT_WRITE = "assignment_write"
    
    # 実績・CSV
    ACTUAL_READ = "actual_read"
    ACTUAL_WRITE = "actual_write"
    AVAILABILITY_READ = "availability_read"
    AVAILABILITY_WRITE = "availability_write"
    CSV_SUBMIT = "csv_submit"
    CSV_IMPORT = "csv_import"
    
    # 請求
    INVOICE_READ = "invoice_read"
    INVOICE_GENERATE = "invoice_generate"
    INVOICE_ISSUE = "invoice_issue"
    INVOICE_CORRECT = "invoice_correct"
    
    # 支払
    PAYOUT_READ = "payout_read"
    PAYOUT_GENERATE = "payout_generate"
    PAYOUT_APPROVE = "payout_approve"
    PAYOUT_CORRECT = "payout_correct"
    
    # 締め
    SOFT_CLOSE = "soft_close"
    SOFT_CLOSE_RELEASE = "soft_close_release"
    HARD_CLOSE = "hard_close"
    HARD_CLOSE_RELEASE = "hard_close_release"
    
    # 経費（仕様17章）
    EXPENSE_READ = "expense_read"
    EXPENSE_SUBMIT = "expense_submit"
    EXPENSE_APPROVE = "expense_approve"
    
    # インセンティブ（仕様18章）
    INCENTIVE_READ = "incentive_read"
    INCENTIVE_CALCULATE = "incentive_calculate"
    INCENTIVE_APPROVE = "incentive_approve"
    
    # 監査ログ
    AUDIT_LOG_READ = "audit_log_read"

    # スタッフ通知
    NOTICE_READ = "notice_read"
    NOTICE_WRITE = "notice_write"


class ClosingStatus(str, Enum):
    """
    締めステータス
    仕様参照: 12.1
    """
    OPEN = "open"                # 未締め
    SOFT_CLOSED = "soft_closed"  # Soft Close
    HARD_CLOSED = "hard_closed"  # Hard Close


class ExpenseStatus(str, Enum):
    """
    経費ステータス
    仕様参照: 17.2
    """
    PENDING = "pending"      # 承認待ち
    APPROVED = "approved"    # 承認済み
    REJECTED = "rejected"    # 却下


class AvailabilityStatus(str, Enum):
    """稼働可否ステータス"""
    AVAILABLE_ALL_DAY = "available_all_day"
    AVAILABLE_AFTER_15 = "available_after_15"
    UNAVAILABLE = "unavailable"
    CONSULT_REQUIRED = "consult_required"
    UNDECIDED = "undecided"


class NoticeType(str, Enum):
    """
    通知種別
    shift_confirm: シフト確定通知
    project_change: 案件変更通知
    general: 一般通知
    """
    SHIFT_CONFIRM = "shift_confirm"
    PROJECT_CHANGE = "project_change"
    GENERAL = "general"


class NoticeTargetType(str, Enum):
    """
    通知対象種別
    all: 全稼働者
    project: 指定案件の稼働者
    worker: 個別稼働者指定
    """
    ALL = "all"
    PROJECT = "project"
    WORKER = "worker"


class IncentiveStatus(str, Enum):
    """
    インセンティブステータス
    仕様参照: 18.3
    """
    PENDING = "pending"      # 承認待ち
    APPROVED = "approved"    # 承認済み
    REJECTED = "rejected"    # 却下
