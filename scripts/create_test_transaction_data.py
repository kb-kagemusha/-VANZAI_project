#!/usr/bin/env python
"""
テストデータ投入（Project, Actual）

本番データ取り込み前の動作確認用
"""
import sys
from pathlib import Path
from datetime import date, time, datetime
from decimal import Decimal

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.deps import SessionLocal
from src.models.master import Worker, Client, Site, Role, ProjectType
from src.models.transaction import Project, Assignment, Actual, ShiftSlot
from src.models.base import generate_ulid
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_test_data():
    """テストデータ作成"""
    db = SessionLocal()
    
    try:
        logger.info("=" * 60)
        logger.info("テストデータ投入開始")
        logger.info("=" * 60)
        
        # マスタデータ取得
        workers = db.query(Worker).limit(3).all()
        clients = db.query(Client).limit(2).all()
        sites = db.query(Site).limit(2).all()
        roles = db.query(Role).limit(2).all()
        project_types = db.query(ProjectType).first()
        
        if not (workers and clients and sites and roles and project_types):
            logger.error("❌ マスタデータが不足しています")
            return
        
        logger.info(f"Workers: {len(workers)}件")
        logger.info(f"Clients: {len(clients)}件")
        logger.info(f"Sites: {len(sites)}件")
        logger.info(f"Roles: {len(roles)}件")
        
        # Project作成
        logger.info("\n[1/3] Project作成...")
        
        project = Project(
            id=generate_ulid(),
            name="テスト案件202601",
            client_id=clients[0].id,
            site_id=sites[0].id,
            project_type_id=project_types.id,
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 31),
            notes="テストプロジェクト"
        )
        db.add(project)
        db.commit()
        logger.info(f"✅ Project作成: {project.name} (id={project.id})")
        
        # ShiftSlot作成（簡易版）
        logger.info("\n[2/4] ShiftSlot作成...")
        
        shift_slots = []
        for day in range(5, 8):  # 1/5, 1/6, 1/7
            for i in range(len(workers)):
                slot = ShiftSlot(
                    id=generate_ulid(),
                    project_id=project.id,
                    shift_label=f"日勤{i+1}",
                    work_date=date(2026, 1, day),
                    start_time=time(9, 0),
                    end_time=time(18, 0)
                )
                db.add(slot)
                shift_slots.append(slot)
        
        db.commit()
        logger.info(f"✅ ShiftSlot作成: {len(shift_slots)}件")
        
        # Assignment作成
        logger.info("\n[3/4] Assignment作成...")
        
        assignments = []
        for i, slot in enumerate(shift_slots):
            assignment = Assignment(
                id=generate_ulid(),
                shift_slot_id=slot.id,
                worker_id=workers[i % len(workers)].id,
                role_id=roles[i % len(roles)].id
            )
            db.add(assignment)
            assignments.append(assignment)
        
        db.commit()
        logger.info(f"✅ Assignment作成: {len(assignments)}件")
        
        # Actual作成（必須フィールドに準拠）
        logger.info("\n[4/4] Actual作成...")
        
        actuals = []
        for assignment in assignments:
            # ShiftSlotから情報を取得
            slot = assignment.shift_slot
            
            actual = Actual(
                id=generate_ulid(),
                project_id=project.id,
                worker_id=assignment.worker_id,
                role_id=assignment.role_id,
                assignment_id=assignment.id,
                import_batch_id="01DUMMY0000000000000000001",  # ダミー
                work_date=slot.work_date,
                period_key="202601",
                start_time=time(9, 0),
                end_time=time(18, 0),
                calc_minutes_total=480,
                calc_minutes_break=60,
                calc_minutes_billable=420,
                applied_price_sales=Decimal("1500.00"),
                applied_price_outsource=Decimal("1000.00"),
                status="active"
            )
            db.add(actual)
            actuals.append(actual)
        
        db.commit()
        logger.info(f"✅ Actual作成: {len(actuals)}件")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ テストデータ投入完了")
        logger.info("=" * 60)
        logger.info(f"Project: 1件")
        logger.info(f"ShiftSlot: {len(shift_slots)}件")
        logger.info(f"Assignment: {len(assignments)}件")
        logger.info(f"Actual: {len(actuals)}件")
        logger.info(f"\n次のステップ:")
        logger.info(f"1. 単価設定を追加: 単価マスタまたはProjectに単価設定が必要")
        logger.info(f"2. API起動: uvicorn src.api.main:app --reload")
        logger.info(f"3. 集計確認: curl http://localhost:8000/api/aggregation/sales?year=2026&month=1")
        logger.info(f"4. 請求書生成テスト")
        
    except Exception as e:
        logger.error(f"❌ エラー: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    create_test_data()
