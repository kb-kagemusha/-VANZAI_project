"""
年月指定で請求書・支払明細を一括生成する。

- 請求書: クライアント単位（月次）
- 支払明細: 稼働者単位（月次）

使い方:
  C:/VANZAI_project/.venv/Scripts/python.exe scripts/generate_monthly_billing.py 202602
"""

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.deps import SessionLocal
from src.services.billing_batch import generate_monthly_billing


def main() -> None:
    if len(sys.argv) < 2:
        print("使用法: python scripts/generate_monthly_billing.py <YYYYMM>")
        sys.exit(1)

    period_key = sys.argv[1].strip()
    if len(period_key) != 6 or not period_key.isdigit():
        print("period_key は YYYYMM 形式で指定してください")
        sys.exit(1)

    db = SessionLocal()
    try:
        result = generate_monthly_billing(
            session=db,
            period_key=period_key,
            user_id="batch_script",
        )
        db.commit()

        print(f"period_key: {period_key}")
        print(f"generated_invoices: {result.generated_invoices}")
        print(f"skipped_invoices: {result.skipped_invoices}")
        print(f"failed_invoices: {len(result.failed_invoices)}")
        print(f"generated_payouts: {result.generated_payouts}")
        print(f"skipped_payouts: {result.skipped_payouts}")
        print(f"failed_payouts: {len(result.failed_payouts)}")

        if result.failed_invoices:
            print("failed_invoices details:")
            for item in result.failed_invoices:
                print(item)
        if result.failed_payouts:
            print("failed_payouts details:")
            for item in result.failed_payouts:
                print(item)
    except Exception as exc:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
