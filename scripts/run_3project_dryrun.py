"""3案件ドライラン（月次フロー）

目的:
    - DRYRUN-202601-01..03 の3案件で月次フローを通す
    - 既存データがある場合はスキップし、重複生成を避ける

実行方法:
    python scripts/run_3project_dryrun.py
"""
import sys
from pathlib import Path
from datetime import date

# プロジェクトルート追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.deps import SessionLocal
from src.models.transaction import Project, Actual, Invoice, Payout
from src.models.enums import InvoiceStatus, PayoutStatus
from src.services import invoice_service, payout_service
from src.services.closing import soft_close, hard_close, get_closing_status

TARGET_PERIOD = "202601"
TARGET_CODES = [
    "DRYRUN-202601-01",
    "DRYRUN-202601-02",
    "DRYRUN-202601-03",
]


def main():
    db = SessionLocal()
    try:
        projects = db.query(Project).filter(Project.code.in_(TARGET_CODES)).all()
        if not projects:
            print("❌ 対象案件が見つかりません。先に create_3project_test_data.py を実行してください")
            return

        for project in projects:
            print("=" * 60)
            print(f"[DRYRUN] {project.code} - {project.name}")

            # 1. Soft Close
            closing = get_closing_status(db, project.id, TARGET_PERIOD)
            if closing.status == "open":
                closing = soft_close(db, project.id, TARGET_PERIOD, user_id="dryrun_ops")
                db.commit()
                print("✅ Soft Close 実行")
            else:
                print(f"⏭️ Soft Close スキップ ({closing.status})")

            # 2. 請求書生成（案件別）
            existing_invoice = db.query(Invoice).filter(
                Invoice.project_id == project.id,
                Invoice.period_key == TARGET_PERIOD,
                Invoice.status != InvoiceStatus.CLOSED.value,
            ).first()
            if existing_invoice:
                print(f"⏭️ 請求書生成スキップ (invoice_id={existing_invoice.id})")
            else:
                invoice = invoice_service.generate_invoice(
                    session=db,
                    client_id=project.client_id,
                    project_id=project.id,
                    period_key=TARGET_PERIOD,
                    billing_date=date(2026, 2, 1),
                    user_id="dryrun_ops",
                )
                db.commit()
                print(f"✅ 請求書生成 (invoice_id={invoice.id}, total={invoice.total_amount})")

            # 3. 支払明細生成（稼働者別）
            worker_ids = [
                row[0]
                for row in db.query(Actual.worker_id)
                .filter(Actual.project_id == project.id, Actual.period_key == TARGET_PERIOD)
                .distinct()
                .all()
            ]
            for worker_id in worker_ids:
                existing_payout = db.query(Payout).filter(
                    Payout.project_id == project.id,
                    Payout.worker_id == worker_id,
                    Payout.period_key == TARGET_PERIOD,
                    Payout.status != PayoutStatus.CLOSED.value,
                ).first()
                if existing_payout:
                    print(f"⏭️ 支払明細スキップ (worker_id={worker_id})")
                    continue

                payout = payout_service.generate_payout(
                    session=db,
                    worker_id=worker_id,
                    project_id=project.id,
                    period_key=TARGET_PERIOD,
                    payment_date=date(2026, 2, 10),
                    user_id="dryrun_ops",
                )
                db.commit()
                print(f"✅ 支払明細生成 (worker_id={worker_id}, total={payout.total_amount})")

            # 4. Hard Close
            closing = get_closing_status(db, project.id, TARGET_PERIOD)
            if closing.status != "hard_closed":
                closing = hard_close(
                    db,
                    project_id=project.id,
                    period_key=TARGET_PERIOD,
                    user_id="dryrun_ops",
                    approver_id="dryrun_approver",
                )
                db.commit()
                print("✅ Hard Close 実行")
            else:
                print("⏭️ Hard Close スキップ (既にhard_closed)")

        print("=" * 60)
        print("✅ 3案件ドライラン完了")

    finally:
        db.close()


if __name__ == "__main__":
    main()
