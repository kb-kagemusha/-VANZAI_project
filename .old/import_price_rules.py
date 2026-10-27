#!/usr/bin/env python
"""
単価マスタ投入（price_sales, price_outsource）

CSV → DB投入
"""
import sys
from pathlib import Path
import csv
from datetime import datetime
from decimal import Decimal

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.deps import SessionLocal
from src.models.master import PriceSales, PriceOutsource
from src.models.base import generate_ulid
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def import_price_sales():
    """販売単価インポート"""
    db = SessionLocal()
    try:
        csv_path = project_root / "kintone_app" / "price_sales_sjis.csv"
        
        with open(csv_path, 'r', encoding='shift_jis') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                # 既存チェック（price_idでユニーク）
                existing = db.query(PriceSales).filter(
                    PriceSales.id == row['price_id']
                ).first()
                
                if existing:
                    logger.info(f"スキップ: {row['price_id']} (既存)")
                    continue
                
                price = PriceSales(
                    id=row['price_id'],
                    client_id=row['client_id'] or None,
                    project_id=row['project_id'] or None,
                    role_id=row['role_id'] or None,
                    unit_price=Decimal(row['unit_price']),
                    valid_from=datetime.strptime(row['valid_from'], "%Y-%m-%d").date() if row['valid_from'] else None,
                    valid_to=datetime.strptime(row['valid_until'], "%Y-%m-%d").date() if row['valid_until'] else None,
                    is_default=row.get('is_default', '') == 'はい',
                    notes=row.get('notes', '') or None
                )
                db.add(price)
                count += 1
        
        db.commit()
        logger.info(f"✅ PriceSales: {count}件投入")
        
    except Exception as e:
        logger.error(f"❌ エラー: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def import_price_outsource():
    """外注単価インポート"""
    db = SessionLocal()
    try:
        csv_path = project_root / "kintone_app" / "price_outsource_sjis.csv"
        
        with open(csv_path, 'r', encoding='shift_jis') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                # 既存チェック（price_idでユニーク）
                existing = db.query(PriceOutsource).filter(
                    PriceOutsource.id == row['price_id']
                ).first()
                
                if existing:
                    logger.info(f"スキップ: {row['price_id']} (既存)")
                    continue
                
                price = PriceOutsource(
                    id=row['price_id'],
                    worker_id=row['worker_id'] or None,
                    project_id=row['project_id'] or None,
                    role_id=row['role_id'] or None,
                    unit_price=Decimal(row['unit_price']),
                    valid_from=datetime.strptime(row['valid_from'], "%Y-%m-%d").date() if row['valid_from'] else None,
                    valid_to=datetime.strptime(row['valid_until'], "%Y-%m-%d").date() if row['valid_until'] else None,
                    is_default=row.get('is_default', '') == 'はい',
                    notes=row.get('notes', '') or None
                )
                db.add(price)
                count += 1
        
        db.commit()
        logger.info(f"✅ PriceOutsource: {count}件投入")
        
    except Exception as e:
        logger.error(f"❌ エラー: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("============================================================")
    logger.info("単価マスタ投入開始")
    logger.info("============================================================")
    
    import_price_sales()
    import_price_outsource()
    
    logger.info("\n✅ 単価マスタ投入完了")
