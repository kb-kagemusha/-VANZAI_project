"""
CSV Import Tests - Sprint1 DoD

必達テスト:
1. 「遅刻修正→再取り込みで二重払いしない」
2. 「canceled assignmentのactualが集計に入らない」

仕様参照:
- 9.4, 9.5, 9.6（CSV取り込み）
- 10.2（アサイン取消）
- 6.3（不変条件: actual.status=activeのみ集計）
"""
import pytest
from datetime import date, time
from decimal import Decimal

from sqlalchemy import select, func

from src.models.base import generate_ulid
from src.models.enums import (
    ActualStatus,
    AssignmentStatus,
    ImportMode,
    ImportScopeType,
    ImportBatchStatus,
)
from src.models.transaction import Actual, Assignment, ShiftSlot
from src.services.csv_import import (
    CsvImportService,
    invalidate_actuals_for_canceled_assignment,
)
from tests.conftest import create_shift_and_assignment


class TestCsvImportNoDuplicatePayment:
    """
    必達テスト1: 遅刻修正→再取り込みで二重払いしない
    
    仕様参照: 9.4, 9.5, 9.6
    - replace_scope で洗い替えし、旧データは superseded にする
    - 集計対象は status=active のみ
    """
    
    def test_reimport_with_time_correction_no_duplicate(
        self,
        session,
        project,
        worker,
        role,
    ):
        """
        シナリオ:
        1. 1月15日の実績をCSV取り込み（09:00-18:00）
        2. 遅刻が判明し、修正CSVを再取り込み（09:30-18:00）
        3. 集計対象は修正後の1件のみ
        
        期待結果:
        - 旧実績は status=superseded
        - 新実績は status=active
        - 集計対象（active）は1件のみ
        """
        # Setup: シフト枠とアサインを作成
        slot, assignment = create_shift_and_assignment(
            session, project, worker, role, date(2026, 1, 15)
        )
        session.commit()
        
        service = CsvImportService(session)
        
        # 1回目: 元のCSV取り込み（09:00-18:00）
        csv1 = f"""worker_id,role_id,work_date,start_time,end_time,break_minutes
{worker.id},{role.id},2026-01-15,09:00,18:00,60
"""
        result1 = service.import_csv(
            file_content=csv1,
            file_name="actuals_202601_v1.csv",
            project_id=project.id,
            period_key="202601",
            mode=ImportMode.REPLACE_SCOPE,
            scope_type=ImportScopeType.PROJECT_MONTH,
            default_price_sales=Decimal("1000"),
            default_price_outsource=Decimal("800"),
        )
        
        assert result1.status in [ImportBatchStatus.COMPLETED, ImportBatchStatus.PARTIAL_ERROR]
        assert result1.count_success == 1
        
        # 確認: 1件のactive実績
        active_count_1 = session.execute(
            select(func.count()).select_from(Actual).where(
                Actual.project_id == project.id,
                Actual.status == ActualStatus.ACTIVE.value,
            )
        ).scalar()
        assert active_count_1 == 1
        
        # 2回目: 遅刻修正CSVを再取り込み（09:30-18:00）
        csv2 = f"""worker_id,role_id,work_date,start_time,end_time,break_minutes
{worker.id},{role.id},2026-01-15,09:30,18:00,60
"""
        result2 = service.import_csv(
            file_content=csv2,
            file_name="actuals_202601_v2.csv",
            project_id=project.id,
            period_key="202601",
            mode=ImportMode.REPLACE_SCOPE,
            scope_type=ImportScopeType.PROJECT_MONTH,
            default_price_sales=Decimal("1000"),
            default_price_outsource=Decimal("800"),
        )
        
        assert result2.status == ImportBatchStatus.COMPLETED
        assert result2.count_success == 1
        assert result2.count_superseded == 1  # 旧データがsuperseded
        
        # 検証: activeな実績は1件のみ（二重化していない）
        active_count_2 = session.execute(
            select(func.count()).select_from(Actual).where(
                Actual.project_id == project.id,
                Actual.status == ActualStatus.ACTIVE.value,
            )
        ).scalar()
        assert active_count_2 == 1, "二重払いの原因となる二重登録が発生"
        
        # 検証: superseded実績は1件
        superseded_count = session.execute(
            select(func.count()).select_from(Actual).where(
                Actual.project_id == project.id,
                Actual.status == ActualStatus.SUPERSEDED.value,
            )
        ).scalar()
        assert superseded_count == 1
        
        # 検証: active実績の時間が修正後の値
        active_actual = session.execute(
            select(Actual).where(
                Actual.project_id == project.id,
                Actual.status == ActualStatus.ACTIVE.value,
            )
        ).scalar_one()
        assert active_actual.start_time == time(9, 30)  # 修正後の開始時刻
    
    def test_reimport_multiple_days_partial_correction(
        self,
        session,
        project,
        worker,
        role,
    ):
        """
        シナリオ:
        1. 1月の3日分の実績を取り込み
        2. 1日分を修正して再取り込み（scope=project_month）
        3. 全日分が正しく洗い替えされる
        
        期待結果:
        - 旧3件は superseded
        - 新3件は active
        - 二重化なし
        """
        # Setup: 3日分のシフト枠とアサイン
        dates = [date(2026, 1, 15), date(2026, 1, 16), date(2026, 1, 17)]
        for d in dates:
            create_shift_and_assignment(session, project, worker, role, d)
        session.commit()
        
        service = CsvImportService(session)
        
        # 1回目: 3日分取り込み
        csv1 = f"""worker_id,role_id,work_date,start_time,end_time,break_minutes
{worker.id},{role.id},2026-01-15,09:00,18:00,60
{worker.id},{role.id},2026-01-16,09:00,18:00,60
{worker.id},{role.id},2026-01-17,09:00,18:00,60
"""
        result1 = service.import_csv(
            file_content=csv1,
            file_name="actuals_202601_v1.csv",
            project_id=project.id,
            period_key="202601",
            mode=ImportMode.REPLACE_SCOPE,
            scope_type=ImportScopeType.PROJECT_MONTH,
            default_price_sales=Decimal("1000"),
            default_price_outsource=Decimal("800"),
        )
        assert result1.count_success == 3
        
        # 2回目: 1/16を遅刻修正して再取り込み
        csv2 = f"""worker_id,role_id,work_date,start_time,end_time,break_minutes
{worker.id},{role.id},2026-01-15,09:00,18:00,60
{worker.id},{role.id},2026-01-16,10:00,18:00,60
{worker.id},{role.id},2026-01-17,09:00,18:00,60
"""
        result2 = service.import_csv(
            file_content=csv2,
            file_name="actuals_202601_v2.csv",
            project_id=project.id,
            period_key="202601",
            mode=ImportMode.REPLACE_SCOPE,
            scope_type=ImportScopeType.PROJECT_MONTH,
            default_price_sales=Decimal("1000"),
            default_price_outsource=Decimal("800"),
        )
        
        assert result2.count_success == 3
        assert result2.count_superseded == 3
        
        # 検証: active件数
        active_count = session.execute(
            select(func.count()).select_from(Actual).where(
                Actual.project_id == project.id,
                Actual.status == ActualStatus.ACTIVE.value,
            )
        ).scalar()
        assert active_count == 3, "二重化発生"
        
        # 検証: 1/16の開始時刻が修正後
        actual_16 = session.execute(
            select(Actual).where(
                Actual.project_id == project.id,
                Actual.work_date == date(2026, 1, 16),
                Actual.status == ActualStatus.ACTIVE.value,
            )
        ).scalar_one()
        assert actual_16.start_time == time(10, 0)


class TestCanceledAssignmentExclusion:
    """
    必達テスト2: canceled assignmentのactualが集計に入らない
    
    仕様参照: 6.3, 10.2
    - assignment.status=canceled に紐づく actual は集計対象外
    - actual.status=invalid に変更して除外
    """
    
    def test_import_rejected_for_canceled_assignment(
        self,
        session,
        project,
        worker,
        role,
    ):
        """
        シナリオ:
        - アサインがcanceledの状態でCSV取り込み
        
        期待結果:
        - 取り込みエラーになる
        - actualが作成されない
        """
        # Setup: canceledアサインを作成
        slot, assignment = create_shift_and_assignment(
            session, project, worker, role, date(2026, 1, 15),
            status=AssignmentStatus.CANCELED,
        )
        session.commit()
        
        service = CsvImportService(session)
        
        csv = f"""worker_id,role_id,work_date,start_time,end_time,break_minutes
{worker.id},{role.id},2026-01-15,09:00,18:00,60
"""
        result = service.import_csv(
            file_content=csv,
            file_name="actuals_202601.csv",
            project_id=project.id,
            period_key="202601",
            mode=ImportMode.REPLACE_SCOPE,
            scope_type=ImportScopeType.PROJECT_MONTH,
            default_price_sales=Decimal("1000"),
            default_price_outsource=Decimal("800"),
        )
        
        # 検証: エラーになる
        assert result.count_error == 1
        assert result.count_success == 0
        assert any("canceled" in e.message for e in result.errors)
    
    def test_invalidate_actuals_when_assignment_canceled(
        self,
        session,
        project,
        worker,
        role,
    ):
        """
        シナリオ:
        1. 正常にCSV取り込み
        2. アサインをキャンセル
        3. 紐づくactualを無効化
        
        期待結果:
        - actual.status=invalid
        - 集計対象から除外される
        """
        # Setup: 正常なアサイン
        slot, assignment = create_shift_and_assignment(
            session, project, worker, role, date(2026, 1, 15),
        )
        session.commit()
        
        service = CsvImportService(session)
        
        # CSV取り込み
        csv = f"""worker_id,role_id,work_date,start_time,end_time,break_minutes
{worker.id},{role.id},2026-01-15,09:00,18:00,60
"""
        result = service.import_csv(
            file_content=csv,
            file_name="actuals_202601.csv",
            project_id=project.id,
            period_key="202601",
            mode=ImportMode.REPLACE_SCOPE,
            scope_type=ImportScopeType.PROJECT_MONTH,
            default_price_sales=Decimal("1000"),
            default_price_outsource=Decimal("800"),
        )
        assert result.count_success == 1
        
        # 確認: active実績あり
        active_before = session.execute(
            select(func.count()).select_from(Actual).where(
                Actual.status == ActualStatus.ACTIVE.value,
            )
        ).scalar()
        assert active_before == 1
        
        # アサインキャンセル + actual無効化
        invalidated_ids = invalidate_actuals_for_canceled_assignment(
            session=session,
            assignment_id=assignment.id,
            reason="Worker no-show",
            actor="admin",
        )
        session.commit()
        
        assert len(invalidated_ids) == 1
        
        # 検証: active実績なし（集計対象外）
        active_after = session.execute(
            select(func.count()).select_from(Actual).where(
                Actual.status == ActualStatus.ACTIVE.value,
            )
        ).scalar()
        assert active_after == 0, "canceled assignmentのactualが集計に残っている"
        
        # 検証: invalid実績あり
        invalid_count = session.execute(
            select(func.count()).select_from(Actual).where(
                Actual.status == ActualStatus.INVALID.value,
            )
        ).scalar()
        assert invalid_count == 1
        
        # 検証: invalid_reasonがセットされている
        invalid_actual = session.execute(
            select(Actual).where(Actual.status == ActualStatus.INVALID.value)
        ).scalar_one()
        assert invalid_actual.invalid_reason == "Worker no-show"
    
    def test_aggregate_only_active_status(
        self,
        session,
        project,
        worker,
        role,
    ):
        """
        集計クエリのテスト:
        - active, invalid, superseded 混在時に
        - status=active のみが集計対象になることを確認
        
        仕様参照: 6.3 不変条件
        """
        # Setup: 複数日分のアサイン
        dates = [date(2026, 1, 15), date(2026, 1, 16), date(2026, 1, 17)]
        assignments = []
        for d in dates:
            _, a = create_shift_and_assignment(session, project, worker, role, d)
            assignments.append(a)
        session.commit()
        
        service = CsvImportService(session)
        
        # 3日分取り込み
        csv = f"""worker_id,role_id,work_date,start_time,end_time,break_minutes
{worker.id},{role.id},2026-01-15,09:00,18:00,60
{worker.id},{role.id},2026-01-16,09:00,18:00,60
{worker.id},{role.id},2026-01-17,09:00,18:00,60
"""
        result = service.import_csv(
            file_content=csv,
            file_name="actuals_202601_v1.csv",
            project_id=project.id,
            period_key="202601",
            mode=ImportMode.REPLACE_SCOPE,
            scope_type=ImportScopeType.PROJECT_MONTH,
            default_price_sales=Decimal("1000"),
            default_price_outsource=Decimal("800"),
        )
        assert result.count_success == 3
        
        # 1/15のactualをinvalidに
        invalidate_actuals_for_canceled_assignment(
            session, assignments[0].id, "Canceled", "admin"
        )
        
        # 再取り込みで1/16, 1/17をsuperseded → 新activeに
        csv2 = f"""worker_id,role_id,work_date,start_time,end_time,break_minutes
{worker.id},{role.id},2026-01-16,09:00,18:00,60
{worker.id},{role.id},2026-01-17,09:00,18:00,60
"""
        result2 = service.import_csv(
            file_content=csv2,
            file_name="actuals_202601_v2.csv",
            project_id=project.id,
            period_key="202601",
            mode=ImportMode.REPLACE_SCOPE,
            scope_type=ImportScopeType.PROJECT_MONTH,
            default_price_sales=Decimal("1000"),
            default_price_outsource=Decimal("800"),
        )
        session.commit()
        
        # 検証: 各ステータスの件数
        status_counts = {}
        for status in [ActualStatus.ACTIVE, ActualStatus.INVALID, ActualStatus.SUPERSEDED]:
            count = session.execute(
                select(func.count()).select_from(Actual).where(
                    Actual.project_id == project.id,
                    Actual.status == status.value,
                )
            ).scalar()
            status_counts[status.value] = count
        
        assert status_counts[ActualStatus.ACTIVE.value] == 2  # 1/16, 1/17の新版
        assert status_counts[ActualStatus.INVALID.value] == 1  # 1/15
        assert status_counts[ActualStatus.SUPERSEDED.value] == 2  # 1/16, 1/17の旧版
        
        # 集計クエリ: activeのみ
        total_billable = session.execute(
            select(func.sum(Actual.calc_minutes_billable)).where(
                Actual.project_id == project.id,
                Actual.status == ActualStatus.ACTIVE.value,
            )
        ).scalar()
        
        # 2日分 × (18:00-09:00=540分 - 60分休憩 = 480分) → 丸め後の値
        # ceil(480/15)*15 = 480分 × 2 = 960分
        assert total_billable == 960, f"集計が不正: {total_billable}"


class TestDuplicateImportPrevention:
    """
    同一ファイル二重取込防止テスト
    
    仕様参照: DEC-001
    """
    
    def test_duplicate_file_rejected(
        self,
        session,
        project,
        worker,
        role,
    ):
        """
        同一ファイル（同一ハッシュ）の再取り込みはエラー
        """
        slot, assignment = create_shift_and_assignment(
            session, project, worker, role, date(2026, 1, 15)
        )
        session.commit()
        
        service = CsvImportService(session)
        
        csv = f"""worker_id,role_id,work_date,start_time,end_time,break_minutes
{worker.id},{role.id},2026-01-15,09:00,18:00,60
"""
        # 1回目
        result1 = service.import_csv(
            file_content=csv,
            file_name="actuals.csv",
            project_id=project.id,
            period_key="202601",
            default_price_sales=Decimal("1000"),
            default_price_outsource=Decimal("800"),
        )
        assert result1.count_success == 1
        
        # 2回目: 同一内容
        result2 = service.import_csv(
            file_content=csv,
            file_name="actuals.csv",
            project_id=project.id,
            period_key="202601",
            default_price_sales=Decimal("1000"),
            default_price_outsource=Decimal("800"),
        )
        
        # 検証: 二重取込拒否
        assert result2.status == ImportBatchStatus.FAILED
        assert any("Duplicate" in e.message for e in result2.errors)
