"""3案件分のテストデータ作成（月次ドライラン用）

目的:
    - 3案件×1期間（202601）の完全なテストデータを作成
    - CSV取込→請求/支払→締め までの一連フローをテスト可能にする

実行方法:
    python scripts/create_3project_test_data.py
"""
import sys
from pathlib import Path
from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal

# プロジェクトルート追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.deps import SessionLocal
from src.models.base import generate_ulid
from src.models.master import Client, Worker, Role, Site, ProjectType, PriceSales, PriceOutsource, IncentiveRule
from src.models.transaction import (
    Project,
    ShiftSlot,
    Assignment,
    Actual,
    Expense,
    Incentive,
    ImportBatch,
)
from src.models.enums import AssignmentStatus, ActualStatus, ExpenseStatus, IncentiveStatus, ImportMode, ImportScopeType, ImportBatchStatus
import hashlib
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def create_3project_test_data():
    """3案件分のテストデータを作成"""
    
    logger.info("=" * 80)
    logger.info("3案件テストデータ作成開始")
    logger.info("=" * 80)
    
    db = SessionLocal()
    
    try:
        # 既存データ確認
        target_period = "202601"
        target_codes = [
            f"DRYRUN-{target_period}-01",
            f"DRYRUN-{target_period}-02",
            f"DRYRUN-{target_period}-03",
        ]
        
        # マスタデータ取得
        workers = db.query(Worker).limit(6).all()
        clients = db.query(Client).limit(3).all()
        sites = db.query(Site).limit(3).all()
        roles = db.query(Role).limit(2).all()
        project_types = db.query(ProjectType).all()
        
        if not all([workers, clients, sites, roles]):
            logger.error("❌ マスタデータが不足しています。先に import_master_data.py を実行してください")
            return
        
        logger.info(f"\n✅ マスタデータ確認:")
        logger.info(f"  Workers: {len(workers)}")
        logger.info(f"  Clients: {len(clients)}")
        logger.info(f"  Sites: {len(sites)}")
        logger.info(f"  Roles: {len(roles)}")
        logger.info(f"  ProjectTypes: {len(project_types)}")

        # Kintone側のtype_id（PT01/02/03）に合わせた案件種別を補完
        pt_targets = [
            ("PT01", "案件種別PT01", "ドライラン用種別1"),
            ("PT02", "案件種別PT02", "ドライラン用種別2"),
            ("PT03", "案件種別PT03", "ドライラン用種別3"),
        ]
        now_utc = datetime.now(timezone.utc)
        for code, name, desc in pt_targets:
            existing_pt = db.query(ProjectType).filter(ProjectType.code == code).first()
            if not existing_pt:
                pt = ProjectType(
                    id=generate_ulid(),
                    code=code,
                    name=name,
                    description=desc,
                    created_at=now_utc,
                    updated_at=now_utc,
                )
                db.add(pt)
        db.flush()

        # ドライラン用の案件種別を優先して使用
        project_types = db.query(ProjectType).filter(
            ProjectType.code.in_([pt[0] for pt in pt_targets])
        ).all()
        
        # 単価設定（共通）
        price_sales_list = []
        price_outsource_list = []
        
        for i, role in enumerate(roles):
            existing_sales = db.query(PriceSales).filter(
                PriceSales.role_id == role.id,
                PriceSales.is_default == True,
            ).first()
            if not existing_sales:
                ps = PriceSales(
                    id=generate_ulid(),
                    role_id=role.id,
                    unit_price=Decimal("1500") + Decimal(i * 200),
                    valid_from=date(2026, 1, 1),
                    is_default=True,
                )
                price_sales_list.append(ps)
                db.add(ps)

            existing_outsource = db.query(PriceOutsource).filter(
                PriceOutsource.role_id == role.id,
                PriceOutsource.is_default == True,
            ).first()
            if not existing_outsource:
                po = PriceOutsource(
                    id=generate_ulid(),
                    role_id=role.id,
                    unit_price=Decimal("1200") + Decimal(i * 150),
                    valid_from=date(2026, 1, 1),
                    is_default=True,
                )
                price_outsource_list.append(po)
                db.add(po)
        
        db.flush()
        logger.info(f"\n✅ 単価マスタ作成: 売上{len(price_sales_list)}件、外注{len(price_outsource_list)}件")
        
        # インセンティブルール（共通）
        incentive_rule = db.query(IncentiveRule).filter(
            IncentiveRule.name == "ドライランルール",
            IncentiveRule.is_active == True,
        ).first()

        if not incentive_rule:
            now_utc = datetime.now(timezone.utc)
            incentive_rule = IncentiveRule(
                id=generate_ulid(),
                name="ドライランルール",
                condition_type="manual",
                condition_json={"note": "dryrun"},
                incentive_amount=Decimal("3000"),
                is_for_invoice=True,
                is_for_payout=True,
                valid_from=date(2026, 1, 1),
                valid_until=None,
                is_active=True,
                notes="ドライラン用ルール",
                created_at=now_utc,
                updated_at=now_utc,
            )
            db.add(incentive_rule)
            db.flush()
        
        # 3案件作成
        projects = []
        for i, code in enumerate(target_codes):
            existing_project = db.query(Project).filter(Project.code == code).first()
            if existing_project:
                projects.append(existing_project)
                continue

            project = Project(
                id=generate_ulid(),
                code=code,
                name=f"ドライラン案件{i+1}",
                client_id=clients[i % len(clients)].id,
                site_id=sites[i % len(sites)].id,
                project_type_id=project_types[i % len(project_types)].id,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
                is_active=True,
            )
            projects.append(project)
            db.add(project)
        
        db.flush()
        logger.info(f"\n✅ 案件作成: {len(projects)}件")
        for p in projects:
            logger.info(f"  - {p.code}: {p.name}")
        
        # 各案件にシフト・アサイン・実績を作成
        total_actuals = 0
        for project in projects:
            logger.info(f"\n[{project.code}] データ作成中...")

            # import_batch作成（project×period）
            file_name = f"dryrun_{project.code}_{target_period}.csv"
            file_hash = hashlib.sha256(file_name.encode("utf-8")).hexdigest()

            import_batch = db.query(ImportBatch).filter(
                ImportBatch.project_id == project.id,
                ImportBatch.period_key == target_period,
                ImportBatch.file_hash == file_hash,
            ).first()

            if not import_batch:
                import_batch = ImportBatch(
                    id=generate_ulid(),
                    submitted_by="dryrun",
                    submit_channel="system_upload",
                    file_name=file_name,
                    file_hash=file_hash,
                    project_id=project.id,
                    period_key=target_period,
                    mode=ImportMode.REPLACE_SCOPE.value,
                    scope_type=ImportScopeType.PROJECT_MONTH.value,
                    status=ImportBatchStatus.COMPLETED.value,
                )
                db.add(import_batch)
                db.flush()

            created_slots = 0
            created_assignments = 0
            created_actuals = 0

            slots = db.query(ShiftSlot).filter(
                ShiftSlot.project_id == project.id,
                ShiftSlot.work_date >= date(2026, 1, 1),
                ShiftSlot.work_date <= date(2026, 1, 5),
            ).all()

            if not slots:
                # 5日分のシフト作成
                for day in range(1, 6):  # 1/1～1/5
                    work_date = date(2026, 1, day)

                    # 1日2シフト（早番・遅番）
                    for shift_idx, (start_h, end_h) in enumerate([(8, 17), (17, 2)]):
                        start_t = time(start_h, 0)
                        end_t = time(end_h if end_h > start_h else end_h, 0)

                        slot = ShiftSlot(
                            id=generate_ulid(),
                            project_id=project.id,
                            work_date=work_date,
                            start_time=start_t,
                            end_time=end_t,
                            required_count=2,
                        )
                        db.add(slot)
                        db.flush()
                        created_slots += 1
                        slots.append(slot)

            if not slots:
                logger.info("  ⚠️ シフトが作成できませんでした")

            for slot in slots:
                assignments = db.query(Assignment).filter(
                    Assignment.shift_slot_id == slot.id,
                ).all()

                if not assignments:
                    for worker_idx in range(2):
                        worker = workers[(slot.work_date.day + worker_idx) % len(workers)]
                        role = roles[worker_idx % len(roles)]

                        assignment = Assignment(
                            id=generate_ulid(),
                            shift_slot_id=slot.id,
                            worker_id=worker.id,
                            role_id=role.id,
                            status=AssignmentStatus.CONFIRMED.value,
                        )
                        db.add(assignment)
                        db.flush()
                        created_assignments += 1
                        assignments.append(assignment)

                for assignment in assignments:
                    existing_actual = db.query(Actual).filter(
                        Actual.assignment_id == assignment.id,
                        Actual.period_key == target_period,
                    ).first()
                    if existing_actual:
                        continue

                    start_t = slot.start_time or time(8, 0)
                    end_t = slot.end_time or time(17, 0)

                    actual_start = datetime.combine(slot.work_date, start_t)
                    actual_end = datetime.combine(
                        slot.work_date if end_t > start_t else slot.work_date + timedelta(days=1),
                        end_t,
                    )

                    total_hours = (actual_end - actual_start).total_seconds() / 3600
                    break_minutes = 60 if total_hours >= 8 else 0

                    actual = Actual(
                        id=generate_ulid(),
                        assignment_id=assignment.id,
                        project_id=project.id,
                        worker_id=assignment.worker_id,
                        role_id=assignment.role_id,
                        import_batch_id=import_batch.id,
                        work_date=slot.work_date,
                        start_time=start_t,
                        end_time=end_t,
                        break_minutes_input=break_minutes,
                        period_key=target_period,
                        status=ActualStatus.ACTIVE.value,
                        applied_price_sales=Decimal("1500"),
                        applied_price_outsource=Decimal("1200"),
                        calc_minutes_total=int(total_hours * 60),
                        calc_minutes_break=break_minutes,
                        calc_minutes_billable=int(total_hours * 60) - break_minutes,
                        calc_minutes_night=0,
                    )
                    db.add(actual)
                    total_actuals += 1
                    created_actuals += 1

            now_utc = datetime.now(timezone.utc)

            # 経費（1件）
            existing_expense = db.query(Expense).filter(
                Expense.project_id == project.id,
                Expense.expense_date == date(2026, 1, 3),
            ).first()
            if not existing_expense:
                expense = Expense(
                    id=generate_ulid(),
                    project_id=project.id,
                    worker_id=workers[0].id,
                    expense_date=date(2026, 1, 3),
                    category="交通費",
                    amount=Decimal("1500"),
                    description="ドライラン経費",
                    status=ExpenseStatus.APPROVED.value,
                    approved_by="dryrun",
                    approved_at=now_utc,
                    target_invoice=True,
                    target_payout=True,
                    created_at=now_utc,
                    updated_at=now_utc,
                )
                db.add(expense)

            # インセンティブ（1件）
            existing_incentive = db.query(Incentive).filter(
                Incentive.project_id == project.id,
                Incentive.period_key == target_period,
            ).first()
            if not existing_incentive:
                incentive = Incentive(
                    id=generate_ulid(),
                    incentive_rule_id=incentive_rule.id,
                    worker_id=workers[0].id,
                    project_id=project.id,
                    period_key=target_period,
                    amount=Decimal("3000"),
                    reason="ドライランインセンティブ",
                    status=IncentiveStatus.APPROVED.value,
                    approved_by="dryrun",
                    approved_at=now_utc,
                    created_at=now_utc,
                    updated_at=now_utc,
                )
                db.add(incentive)

            slot_count = db.query(ShiftSlot).filter(
                ShiftSlot.project_id == project.id,
                ShiftSlot.work_date >= date(2026, 1, 1),
                ShiftSlot.work_date <= date(2026, 1, 5),
            ).count()
            assignment_count = db.query(Assignment).join(
                ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id
            ).filter(ShiftSlot.project_id == project.id).count()
            actual_count = db.query(Actual).filter(
                Actual.project_id == project.id,
                Actual.period_key == target_period,
            ).count()

            logger.info(
                f"  ✅ 追加: シフト{created_slots}枠/アサイン{created_assignments}件/実績{created_actuals}件"
            )
            logger.info(
                f"  📊 合計: シフト{slot_count}枠/アサイン{assignment_count}件/実績{actual_count}件/経費1件/インセンティブ1件"
            )
        
        db.commit()
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ 3案件テストデータ作成完了")
        logger.info("=" * 80)
        logger.info(f"案件: {len(projects)}件")
        logger.info(f"実績: {total_actuals}件")
        logger.info("\n次のステップ:")
        logger.info("  1. python scripts/sync_db_to_kintone.py all")
        logger.info("  2. 月次ドライランの実施")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    create_3project_test_data()
