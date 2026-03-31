#!/usr/bin/env python
"""簡易請求書生成テスト"""
import sys
from pathlib import Path
from datetime import date
from decimal import Decimal

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.deps import SessionLocal
from src.models.transaction import Invoice, InvoiceLine, Actual, Project
from src.models.master import Client
from src.models.enums import InvoiceStatus, LineType
from src.models.base import generate_ulid

db = SessionLocal()

try:
    # プロジェクトとクライアント取得
    project_id = "01KG1E9J0B16HQ6X8QMS24TXSD"
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        print("❌ Project not found")
        sys.exit(1)
    
    client = db.query(Client).filter(Client.id == project.client_id).first()
    
    if not client:
        print("❌ Client not found")
        sys.exit(1)
    
    # Actual集計
    actuals = db.query(Actual).filter(
        Actual.project_id == project_id,
        Actual.period_key == "202601",
        Actual.status == "active"
    ).all()
    
    print(f"✅ Project: {project.id}")
    print(f"✅ Client: {client.name}")
    print(f"✅ Actuals: {len(actuals)}件")
    
    # 請求書作成
    total_amount = sum(
        Decimal(str(a.calc_minutes_billable / 60)) * a.applied_price_sales 
        for a in actuals
    )
    
    invoice = Invoice(
        id=generate_ulid(),
        client_id=client.id,
        project_id=project.id,
        period_key="202601",
        billing_date=date(2026, 1, 31),
        status=InvoiceStatus.PREPARING,
        version=1,
        subtotal=Decimal(str(total_amount)),
        tax_amount=Decimal(str(total_amount * Decimal("0.1"))),
        total_amount=Decimal(str(total_amount * Decimal("1.1")))
    )
    db.add(invoice)
    
    # 明細行作成
    for idx, actual in enumerate(actuals, start=1):
        hours = Decimal(str(actual.calc_minutes_billable / 60))
        line = InvoiceLine(
            id=generate_ulid(),
            invoice_id=invoice.id,
            line_number=idx,
            line_type=LineType.WORK,
            description=f"{actual.work_date} 稼働: {actual.worker.name} / {actual.role.name}",
            quantity_snapshot=hours,
            unit_price_snapshot=actual.applied_price_sales,
            unit_type="hours",
            line_amount=hours * actual.applied_price_sales
        )
        db.add(line)
    
    db.commit()
    
    print(f"\n✅ 請求書生成成功")
    print(f"  Invoice ID: {invoice.id}")
    print(f"  請求額: ¥{invoice.total_amount:,.0f}")
    print(f"  明細行: {len(actuals)}件")

except Exception as e:
    print(f"❌ エラー: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()
