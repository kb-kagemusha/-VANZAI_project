"""
カスタム例外定義
仕様参照: DESIGN_SPEC_v0.3.md 全体のエラーハンドリング戦略
"""


class VANZAIException(Exception):
    """
    VANZAI システム基底例外
    
    すべてのカスタム例外はこのクラスを継承する
    """
    def __init__(self, message: str, code: str = "VANZAI_ERROR", details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class PriceNotResolvedException(VANZAIException):
    """
    単価解決失敗
    
    仕様参照: 7章（単価マスタ）
    - 該当する単価マスタが存在しない
    - 有効期間外
    - ロックされた単価が不正
    """
    def __init__(self, message: str = "Price could not be resolved", details: dict = None):
        super().__init__(message, code="PRICE_NOT_RESOLVED", details=details)


class ClosingViolationException(VANZAIException):
    """
    締め後の変更試行
    
    仕様参照: 12章（締め処理）
    - Soft Close後の実績変更
    - Hard Close後の再計算試行
    - 締め解除の権限不足
    """
    def __init__(self, message: str = "Operation violates closing constraints", details: dict = None):
        super().__init__(message, code="CLOSING_VIOLATION", details=details)


class DuplicateImportException(VANZAIException):
    """
    重複取り込み
    
    仕様参照: 9章（CSV取り込み）、Decision DEC-001
    - 同一ファイルハッシュの再取り込み
    - 同一期間×案件×稼働者の重複データ
    """
    def __init__(self, message: str = "Duplicate import detected", details: dict = None):
        super().__init__(message, code="DUPLICATE_IMPORT", details=details)


class InvalidCSVFormatException(VANZAIException):
    """
    CSV形式不正
    
    仕様参照: 9.4（バリデーション）
    - 必須カラム不足
    - データ型不一致
    - フォーマットエラー
    """
    def __init__(self, message: str = "Invalid CSV format", details: dict = None):
        super().__init__(message, code="INVALID_CSV_FORMAT", details=details)


class AssignmentCanceledException(VANZAIException):
    """
    キャンセル済みアサインへの操作
    
    仕様参照: 6.3（不変条件）
    - canceled状態のアサインに実績登録試行
    """
    def __init__(self, message: str = "Assignment is canceled", details: dict = None):
        super().__init__(message, code="ASSIGNMENT_CANCELED", details=details)


class InvoiceAlreadyIssuedException(VANZAIException):
    """
    発行済み請求書の変更試行
    
    仕様参照: 11章（請求書生成）
    - ISSUED状態の請求書への直接変更
    - 訂正せずに金額変更
    """
    def __init__(self, message: str = "Invoice is already issued", details: dict = None):
        super().__init__(message, code="INVOICE_ALREADY_ISSUED", details=details)


class PayoutAlreadyPaidException(VANZAIException):
    """
    支払済み明細の変更試行
    
    仕様参照: 11章（支払明細生成）
    - PAID状態の支払明細への変更
    """
    def __init__(self, message: str = "Payout is already paid", details: dict = None):
        super().__init__(message, code="PAYOUT_ALREADY_PAID", details=details)


class PermissionDeniedException(VANZAIException):
    """
    権限不足
    
    仕様参照: 5章（権限管理）
    - 必要な権限を持たないユーザーの操作試行
    """
    def __init__(self, message: str = "Permission denied", details: dict = None):
        super().__init__(message, code="PERMISSION_DENIED", details=details)


class RecordNotFoundException(VANZAIException):
    """
    レコード不存在
    
    - 指定されたIDのレコードが見つからない
    """
    def __init__(self, message: str = "Record not found", details: dict = None):
        super().__init__(message, code="RECORD_NOT_FOUND", details=details)


class ValidationException(VANZAIException):
    """
    バリデーションエラー
    
    - 入力値の検証失敗
    - 業務ロジック制約違反
    """
    def __init__(self, message: str = "Validation failed", details: dict = None):
        super().__init__(message, code="VALIDATION_ERROR", details=details)
