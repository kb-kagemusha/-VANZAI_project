"""
CSV import service
仕様参照: DESIGN_SPEC_v0.3 セクション9（CSV取り込み仕様）

主要機能:
- replace_scope による洗い替え（9.4, 9.5, 9.6）
- 二重化防止（9.6）
- エラー処理と部分取り込み（6.2）
- 監査ログ出力（16章）

Decision参照:
- DEC-001: import_batch重複検知キー
- DEC-002: period_key形式（YYYYMM）
- DEC-003: アサインなし実績はエラー扱い
"""
import csv
import hashlib
import io
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, BinaryIO

from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.models.base import generate_ulid
from src.models.enums import (
    ActualStatus,
    AssignmentStatus,
    ImportMode,
    ImportScopeType,
    ImportBatchStatus,
)
from src.models.transaction import (
    Actual,
    Assignment,
    ImportBatch,
    Project,
)
from src.services.audit import AuditService
from src.services.time_calc import calculate_time, TimeCalcResult
from src.services.price_resolver import resolve_sales_price, resolve_outsource_price
from src.exceptions import InvalidCSVFormatException, DuplicateImportException


@dataclass
class CsvRow:
    """CSV行データ"""
    row_number: int
    project_id: str
    worker_id: str
    role_id: str
    work_date: date
    start_time: time | None = None
    end_time: time | None = None
    break_minutes: int | None = None
    hours: Decimal | None = None
    notes: str | None = None
    external_row_key: str | None = None
    assignment_id: str | None = None  # 解決後にセット


@dataclass
class ImportError:
    """取り込みエラー"""
    row_number: int
    field: str | None
    message: str
    raw_data: dict | None = None


@dataclass
class ImportResult:
    """取り込み結果"""
    batch_id: str
    status: ImportBatchStatus
    count_success: int = 0
    count_error: int = 0
    count_skip: int = 0
    count_superseded: int = 0
    errors: list[ImportError] = field(default_factory=list)
    has_row_count_warning: bool = False
    has_total_time_warning: bool = False
    warnings: list[str] = field(default_factory=list)


class CsvImportService:
    """
    CSV取り込みサービス
    
    仕様参照: 9章
    AGENTS.md: CSV再取り込みで二重化を起こさない
    """
    
    # 部分ファイル警告の閾値
    ROW_COUNT_WARNING_THRESHOLD = 0.5  # 前回比50%以下なら警告
    TOTAL_TIME_WARNING_THRESHOLD = 0.5  # 前回比50%以下なら警告
    
    def __init__(self, session: Session):
        self.session = session
        self.audit = AuditService(session)
    
    def import_csv(
        self,
        file_content: bytes | str,
        file_name: str,
        project_id: str,
        period_key: str,
        *,
        mode: ImportMode = ImportMode.REPLACE_SCOPE,
        scope_type: ImportScopeType = ImportScopeType.PROJECT_MONTH,
        submitted_by: str | None = None,
        submit_channel: str = "system_upload",
        default_price_sales: Decimal = Decimal("0"),
        default_price_outsource: Decimal = Decimal("0"),
    ) -> ImportResult:
        """
        CSVファイルを取り込む
        
        仕様参照: 9.4, 9.5, 9.6
        
        Args:
            file_content: CSVファイル内容
            file_name: ファイル名
            project_id: 案件ID
            period_key: 期間キー（YYYYMM）
            mode: 取り込みモード
            scope_type: 洗い替えスコープ
            submitted_by: 提出者
            submit_channel: 提出チャネル
            default_price_sales: デフォルト売上単価
            default_price_outsource: デフォルト外注単価
        
        Returns:
            ImportResult
        """
        # ファイルハッシュ計算
        if isinstance(file_content, str):
            file_bytes = file_content.encode('utf-8')
        else:
            file_bytes = file_content
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        
        # 二重取込チェック（DEC-001）
        existing_batch = self.session.execute(
            select(ImportBatch).where(
                ImportBatch.file_hash == file_hash,
                ImportBatch.project_id == project_id,
                ImportBatch.period_key == period_key,
            )
        ).scalar_one_or_none()
        
        if existing_batch:
            return ImportResult(
                batch_id=existing_batch.id,
                status=ImportBatchStatus.FAILED,
                errors=[ImportError(
                    row_number=0,
                    field=None,
                    message=f"Duplicate import: file already imported as batch {existing_batch.id}",
                )],
            )
        
        # プロジェクト取得
        project = self.session.get(Project, project_id)
        if not project:
            return ImportResult(
                batch_id="",
                status=ImportBatchStatus.FAILED,
                errors=[ImportError(
                    row_number=0,
                    field="project_id",
                    message=f"Project not found: {project_id}",
                )],
            )
        
        # ImportBatch作成
        batch = ImportBatch(
            id=generate_ulid(),
            submitted_by=submitted_by,
            submit_channel=submit_channel,
            file_name=file_name,
            file_hash=file_hash,
            project_id=project_id,
            period_key=period_key,
            mode=mode.value,
            scope_type=scope_type.value if scope_type else None,
            status=ImportBatchStatus.PROCESSING.value,
        )
        self.session.add(batch)
        
        # 監査ログ: バッチ作成
        self.audit.log_import_batch_created(
            batch_id=batch.id,
            file_name=file_name,
            mode=mode.value,
            scope_type=scope_type.value if scope_type else None,
            project_id=project_id,
            period_key=period_key,
            actor=submitted_by,
        )
        
        # CSVパース
        rows, parse_errors = self._parse_csv(file_bytes, project_id)
        
        result = ImportResult(
            batch_id=batch.id,
            status=ImportBatchStatus.PROCESSING,
            errors=parse_errors,
            count_error=len(parse_errors),
        )
        
        if not rows and parse_errors:
            # 全行エラー
            batch.status = ImportBatchStatus.FAILED.value
            batch.count_error = len(parse_errors)
            batch.errors_json = [
                {"row": e.row_number, "field": e.field, "message": e.message}
                for e in parse_errors
            ]
            result.status = ImportBatchStatus.FAILED
            self.session.commit()
            return result
        
        # replace_scope: 既存データをsupersededに
        superseded_count = 0
        superseded_ids = []
        if mode == ImportMode.REPLACE_SCOPE:
            superseded_count, superseded_ids = self._supersede_existing(
                project_id=project_id,
                period_key=period_key,
                scope_type=scope_type,
                rows=rows,
            )
            result.count_superseded = superseded_count
            
            # 監査ログ: replace_scope実行
            self.audit.log_replace_scope_executed(
                batch_id=batch.id,
                scope_type=scope_type.value,
                project_id=project_id,
                period_key=period_key,
                superseded_count=superseded_count,
                superseded_ids=superseded_ids,
                actor=submitted_by,
            )
        
        # 部分ファイル警告チェック（仕様9.6）
        self._check_partial_file_warning(
            project_id=project_id,
            period_key=period_key,
            new_row_count=len(rows),
            new_total_minutes=sum(self._estimate_minutes(r) for r in rows),
            result=result,
        )
        
        # 行ごとに処理
        for row in rows:
            try:
                self._process_row(
                    row=row,
                    batch=batch,
                    project=project,
                    default_price_sales=default_price_sales,
                    default_price_outsource=default_price_outsource,
                    result=result,
                )
            except Exception as e:
                result.errors.append(ImportError(
                    row_number=row.row_number,
                    field=None,
                    message=str(e),
                ))
                result.count_error += 1
        
        # バッチ更新
        batch.count_success = result.count_success
        batch.count_error = result.count_error
        batch.count_skip = result.count_skip
        batch.count_superseded = result.count_superseded
        batch.has_row_count_warning = result.has_row_count_warning
        batch.has_total_time_warning = result.has_total_time_warning
        batch.errors_json = [
            {"row": e.row_number, "field": e.field, "message": e.message}
            for e in result.errors
        ] if result.errors else None
        
        if result.count_error > 0 and result.count_success > 0:
            batch.status = ImportBatchStatus.PARTIAL_ERROR.value
            result.status = ImportBatchStatus.PARTIAL_ERROR
        elif result.count_error > 0:
            batch.status = ImportBatchStatus.FAILED.value
            result.status = ImportBatchStatus.FAILED
        else:
            batch.status = ImportBatchStatus.COMPLETED.value
            result.status = ImportBatchStatus.COMPLETED
        
        # 監査ログ: バッチ完了
        self.audit.log_import_batch_completed(
            batch_id=batch.id,
            count_success=result.count_success,
            count_error=result.count_error,
            count_skip=result.count_skip,
            count_superseded=result.count_superseded,
            has_warnings=result.has_row_count_warning or result.has_total_time_warning,
            actor=submitted_by,
        )
        
        self.session.commit()
        return result
    
    def _parse_csv(
        self,
        file_bytes: bytes,
        project_id: str,
    ) -> tuple[list[CsvRow], list[ImportError]]:
        """
        CSVをパースする
        仕様参照: 9.3（CSV列）
        """
        rows = []
        errors = []
        
        try:
            content = file_bytes.decode('utf-8-sig')  # BOM対応
        except UnicodeDecodeError:
            try:
                content = file_bytes.decode('shift_jis')
            except UnicodeDecodeError:
                errors.append(ImportError(
                    row_number=0,
                    field=None,
                    message="Failed to decode file: unsupported encoding",
                ))
                return rows, errors
        
        reader = csv.DictReader(io.StringIO(content))
        
        for i, raw_row in enumerate(reader, start=2):  # 2行目から（ヘッダー除く）
            try:
                row = self._parse_row(raw_row, i, project_id)
                if row:
                    rows.append(row)
            except ValueError as e:
                errors.append(ImportError(
                    row_number=i,
                    field=None,
                    message=str(e),
                    raw_data=raw_row,
                ))
        
        return rows, errors
    
    def _parse_row(
        self,
        raw: dict[str, str],
        row_number: int,
        default_project_id: str,
    ) -> CsvRow | None:
        """
        CSV行をパースする
        仕様参照: 9.3
        """
        # 必須フィールド
        worker_id = raw.get('worker_id', '').strip()
        if not worker_id:
            raise InvalidCSVFormatException("worker_id is required", details={"row": row_number})
        
        role_id = raw.get('role_id', '').strip()
        if not role_id:
            raise InvalidCSVFormatException("role_id is required", details={"row": row_number})
        
        work_date_str = raw.get('work_date', '').strip()
        if not work_date_str:
            raise InvalidCSVFormatException("work_date is required", details={"row": row_number})
        try:
            work_date = date.fromisoformat(work_date_str)
        except ValueError:
            raise InvalidCSVFormatException(f"Invalid work_date format: {work_date_str}", details={"row": row_number})
        
        project_id = raw.get('project_id', '').strip() or default_project_id
        
        # 時間フィールド
        start_time = None
        end_time = None
        hours = None
        
        start_time_str = raw.get('start_time', '').strip()
        end_time_str = raw.get('end_time', '').strip()
        hours_str = raw.get('hours', '').strip()
        
        if start_time_str:
            try:
                start_time = time.fromisoformat(start_time_str)
            except ValueError:
                raise InvalidCSVFormatException(f"Invalid start_time format: {start_time_str}", details={"row": row_number})
        
        if end_time_str:
            try:
                end_time = time.fromisoformat(end_time_str)
            except ValueError:
                raise InvalidCSVFormatException(f"Invalid end_time format: {end_time_str}", details={"row": row_number})
        
        if hours_str:
            try:
                hours = Decimal(hours_str)
            except InvalidOperation:
                raise InvalidCSVFormatException(f"Invalid hours format: {hours_str}", details={"row": row_number})
        
        # start_time または hours が必要
        if not start_time and hours is None:
            raise InvalidCSVFormatException("Either start_time or hours is required", details={"row": row_number})
        
        # start_timeがある場合はend_timeも必要
        if start_time and not end_time:
            raise InvalidCSVFormatException("end_time is required when start_time is provided", details={"row": row_number})
        
        # 休憩
        break_minutes = None
        break_str = raw.get('break_minutes', '').strip()
        if break_str:
            try:
                break_minutes = int(break_str)
            except ValueError:
                raise InvalidCSVFormatException(f"Invalid break_minutes format: {break_str}", details={"row": row_number})
        
        return CsvRow(
            row_number=row_number,
            project_id=project_id,
            worker_id=worker_id,
            role_id=role_id,
            work_date=work_date,
            start_time=start_time,
            end_time=end_time,
            break_minutes=break_minutes,
            hours=hours,
            notes=raw.get('notes', '').strip() or None,
            external_row_key=raw.get('external_row_key', '').strip() or None,
        )
    
    def _supersede_existing(
        self,
        project_id: str,
        period_key: str,
        scope_type: ImportScopeType,
        rows: list[CsvRow],
    ) -> tuple[int, list[str]]:
        """
        既存の実績をsuperseded状態に更新（洗い替え）
        
        仕様参照: 9.6
        AGENTS.md: 旧データは削除しないでsupersededとして残す
        """
        # スコープに応じたクエリ構築
        query = select(Actual).where(
            Actual.project_id == project_id,
            Actual.status == ActualStatus.ACTIVE.value,
        )
        
        if scope_type == ImportScopeType.PROJECT_MONTH:
            query = query.where(Actual.period_key == period_key)
        elif scope_type == ImportScopeType.PROJECT_DAY:
            # 取り込みデータに含まれる日付のみ対象
            work_dates = list(set(r.work_date for r in rows))
            query = query.where(Actual.work_date.in_(work_dates))
        elif scope_type == ImportScopeType.PROJECT_DAY_WORKER:
            # 取り込みデータに含まれる日付×稼働者のみ対象
            from sqlalchemy import tuple_
            day_worker_pairs = list(set((r.work_date, r.worker_id) for r in rows))
            if day_worker_pairs:
                query = query.where(
                    tuple_(Actual.work_date, Actual.worker_id).in_(day_worker_pairs)
                )
        
        existing_actuals = self.session.execute(query).scalars().all()
        
        superseded_ids = []
        for actual in existing_actuals:
            actual.status = ActualStatus.SUPERSEDED.value
            superseded_ids.append(actual.id)
        
        return len(superseded_ids), superseded_ids
    
    def _check_partial_file_warning(
        self,
        project_id: str,
        period_key: str,
        new_row_count: int,
        new_total_minutes: int,
        result: ImportResult,
    ) -> None:
        """
        部分ファイル警告をチェック
        仕様参照: 9.6
        """
        # 前回の取り込みを取得
        prev_batch = self.session.execute(
            select(ImportBatch).where(
                ImportBatch.project_id == project_id,
                ImportBatch.period_key == period_key,
                ImportBatch.status.in_([
                    ImportBatchStatus.COMPLETED.value,
                    ImportBatchStatus.PARTIAL_ERROR.value,
                ]),
            ).order_by(ImportBatch.created_at.desc()).limit(1)
        ).scalar_one_or_none()
        
        if not prev_batch:
            return
        
        prev_row_count = prev_batch.count_success
        
        # 行数チェック
        if prev_row_count > 0:
            ratio = new_row_count / prev_row_count
            if ratio < self.ROW_COUNT_WARNING_THRESHOLD:
                result.has_row_count_warning = True
                result.warnings.append(
                    f"Row count significantly decreased: {prev_row_count} -> {new_row_count} ({ratio:.0%})"
                )
    
    def _estimate_minutes(self, row: CsvRow) -> int:
        """行の推定稼働時間を返す（警告チェック用）"""
        if row.hours:
            return int(row.hours * 60)
        if row.start_time and row.end_time:
            from src.services.time_calc import calculate_total_minutes
            return calculate_total_minutes(row.start_time, row.end_time)
        return 0
    
    def _process_row(
        self,
        row: CsvRow,
        batch: ImportBatch,
        project: Project,
        default_price_sales: Decimal,
        default_price_outsource: Decimal,
        result: ImportResult,
    ) -> None:
        """
        1行を処理してActualを作成
        
        仕様参照: 8.2（時間計算）, 9.3（CSV列）
        DEC-003: アサインなし実績はエラー扱い
        """
        # アサイン解決
        assignment = self._resolve_assignment(row, project.id)
        if not assignment:
            # DEC-003: アサインなし実績はエラー扱い
            result.errors.append(ImportError(
                row_number=row.row_number,
                field="assignment",
                message="No matching assignment found for worker/date combination",
            ))
            result.count_error += 1
            return
        
        # アサインステータスチェック（仕様10.2）
        from src.models.enums import AssignmentStatus
        if assignment.status == AssignmentStatus.CANCELED.value:
            result.errors.append(ImportError(
                row_number=row.row_number,
                field="assignment",
                message=f"Assignment {assignment.id} is canceled",
            ))
            result.count_error += 1
            return
        
        row.assignment_id = assignment.id
        
        # 時間計算（仕様8.2）
        try:
            time_result = calculate_time(
                start_time=row.start_time,
                end_time=row.end_time,
                break_minutes_input=row.break_minutes,
                hours_input=row.hours,
                rounding_unit=project.rounding_unit_minutes,
                rounding_method=project.rounding_method,
                break_rule=project.break_deduction_rule,
                time_calc_mode=project.time_calc_mode,
                night_window_start=project.night_window_start,
                night_window_end=project.night_window_end,
            )
        except ValueError as e:
            result.errors.append(ImportError(
                row_number=row.row_number,
                field="time",
                message=str(e),
            ))
            result.count_error += 1
            return
        
        # 単価決定（仕様7.2, 7.3 - スナップショット保存）
        price_sales = resolve_sales_price(self.session, assignment, row.work_date)
        if price_sales is None:
            price_sales = default_price_sales
        
        price_outsource = resolve_outsource_price(self.session, assignment, row.work_date)
        if price_outsource is None:
            price_outsource = default_price_outsource
        
        # period_key生成（DEC-002: YYYYMM）
        period_key = row.work_date.strftime('%Y%m')
        
        # Actual作成
        actual = Actual(
            id=generate_ulid(),
            project_id=row.project_id,
            worker_id=row.worker_id,
            role_id=row.role_id,
            assignment_id=row.assignment_id,
            import_batch_id=batch.id,
            work_date=row.work_date,
            period_key=period_key,
            status=ActualStatus.ACTIVE.value,
            start_time=row.start_time,
            end_time=row.end_time,
            break_minutes_input=row.break_minutes,
            hours_input=row.hours,
            calc_minutes_total=time_result.minutes_total,
            calc_minutes_break=time_result.minutes_break,
            calc_minutes_billable=time_result.minutes_billable,
            calc_minutes_night=time_result.minutes_night,
            calc_rounding_unit=time_result.rounding_unit,
            calc_rounding_method=time_result.rounding_method,
            calc_break_rule=time_result.break_rule,
            applied_price_sales=price_sales,
            applied_price_outsource=price_outsource,
            external_row_key=row.external_row_key,
            needs_review=time_result.needs_review,
            review_reason=time_result.review_reason,
            notes=row.notes,
        )
        
        self.session.add(actual)
        result.count_success += 1
    
    def _resolve_assignment(
        self,
        row: CsvRow,
        project_id: str,
    ) -> Assignment | None:
        """CSV行に対応するアサインを解決
        
        探索順序:
        1. project_id + work_date + worker_id で shift_slot → assignment を探す
        
        Note: CANCELEDステータスも含めて取得し、呼び出し側でチェックする
        """
        from src.models.transaction import ShiftSlot
        
        # shift_slot経由でassignmentを探す（CANCELEDも含む）
        stmt = (
            select(Assignment)
            .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
            .where(
                ShiftSlot.project_id == project_id,
                ShiftSlot.work_date == row.work_date,
                Assignment.worker_id == row.worker_id,
            )
        )
        return self.session.execute(stmt).scalars().first()


def invalidate_actuals_for_canceled_assignment(
    session: Session,
    assignment_id: str,
    reason: str,
    actor: str | None = None,
) -> list[str]:
    """キャンセルされたアサインに紐づく実績を無効化
    
    仕様参照: 10.2 取消とactual invalid化
    AGENTS.md: canceled assignmentに紐づくactualは集計対象外
    
    Args:
        session: DBセッション
        assignment_id: アサインID
        reason: 無効化理由
        actor: 実行者
    
    Returns:
        無効化されたActualのIDリスト
    """
    audit = AuditService(session)
    
    # activeな実績を取得
    actuals = session.execute(
        select(Actual).where(
            Actual.assignment_id == assignment_id,
            Actual.status == ActualStatus.ACTIVE.value,
        )
    ).scalars().all()
    
    invalidated_ids = []
    for actual in actuals:
        actual.status = ActualStatus.INVALID.value
        actual.invalid_reason = reason
        invalidated_ids.append(actual.id)
        
        # 監査ログ
        audit.log_actual_invalidated(
            actual_id=actual.id,
            reason=reason,
            assignment_id=assignment_id,
            actor=actor,
        )
    
    return invalidated_ids
