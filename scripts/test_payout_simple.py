#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
支払明細生成の簡易テストスクリプト
Task 9: Payout generation test
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from decimal import Decimal
from datetime import date

from src.models.transaction import Actual, Payout, PayoutLine
from src.models.base import generate_ulid
from src.models.enums import PayoutStatus, LineType

# DB接続
engine = create_engine("sqlite:///vanzai.db")
Session = sessionmaker(bind=engine)

try:
    db = Session()
    
    # 2026年1月のテストプロジェクトの実績を取得
    actuals = db.scalars(
        select(Actual)
        .where(Actual.work_date >= date(2026, 1, 1))
        .where(Actual.work_date < date(2026, 2, 1))
        .where(Actual.assignment_id.isnot(None))
    ).all()
    
    print(f"✅ Actuals: {len(actuals)}件")
    
    if not actuals:
        print("❌ 実績データがありません")
        sys.exit(1)
    
    # ワーカー別にグループ化
    worker_actuals = {}
    for actual in actuals:
        if actual.worker_id not in worker_actuals:
            worker_actuals[actual.worker_id] = []
        worker_actuals[actual.worker_id].append(actual)
    
    print(f"✅ ワーカー: {len(worker_actuals)}人")
    
    # 各ワーカーの支払明細を生成
    for worker_id, worker_acts in worker_actuals.items():
        first_actual = worker_acts[0]
        worker = first_actual.worker
        
        # 支払総額を計算
        total = sum(
            Decimal(str(act.calc_minutes_billable / 60)) * act.applied_price_outsource
            for act in worker_acts
        )
        
        # Payout作成
        payout = Payout(
            id=generate_ulid(),
            worker_id=worker_id,
            period_key="2026-01",
            payment_date=date(2026, 2, 28),  # 翌月末払い
            status=PayoutStatus.PREPARING,
            total_amount=total
        )
        db.add(payout)
        
        # PayoutLine作成
        for idx, actual in enumerate(worker_acts, start=1):
            hours = Decimal(str(actual.calc_minutes_billable / 60))
            line = PayoutLine(
                id=generate_ulid(),
                payout_id=payout.id,
                line_number=idx,
                line_type=LineType.WORK,
                description=f"{actual.work_date} 稼働: {actual.project.name} / {actual.role.name}",
                quantity_snapshot=hours,
                unit_price_snapshot=actual.applied_price_outsource,
                unit_type="hours",
                line_amount=hours * actual.applied_price_outsource
            )
            db.add(line)
        
        print(f"✅ {worker.name}: ¥{total:,.0f} ({len(worker_acts)}件)")
    
    db.commit()
    
    # 検証
    payouts = db.scalars(select(Payout)).all()
    print(f"\n✅ 支払明細生成成功")
    print(f"  Payout: {len(payouts)}件")
    print(f"  総支払額: ¥{sum(p.total_amount for p in payouts):,.0f}")
    
except Exception as e:
    print(f"❌ エラー: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()
