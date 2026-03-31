"""actual.applied_price_* を手動調整する運用ツール（バンドル価格対応）

背景（DEC-009 / docs/ops/DRV_PAYOUT_RULES.md）:
- Wヘッダー等で「バンドル価格」を採用する場合、自動判定は行わず都度手入力で調整する
- 当面は actual.applied_price_sales を直接編集する運用
- ただし、締め後や発行済み請求/承認済み支払に影響する変更は事故るため禁止する

このスクリプトは安全のためデフォルトで dry-run です。

使用例:
    # 単体（dry-run）
    python scripts/adjust_actual_applied_prices.py --actual-id ACTUAL_ID --sales 35000 --reason "Wヘッダーのバンドル調整"

    # 単体（実反映）
    python scripts/adjust_actual_applied_prices.py --actual-id ACTUAL_ID --sales 35000 --reason "Wヘッダーのバンドル調整" --actor ops_user --commit

    # CSV一括（dry-run）
    python scripts/adjust_actual_applied_prices.py --csv scripts/sample/actual_price_adjustments.csv

    # CSV一括（実反映）
    python scripts/adjust_actual_applied_prices.py --csv scripts/sample/actual_price_adjustments.csv --actor ops_user --commit

CSV形式:
    actual_id,applied_price_sales,applied_price_outsource,reason
    01H...,35000,,Wヘッダーのバンドル調整

注意:
- 発行済み請求（issued/closed）または承認済み支払（approved/paid/closed）に含まれる actual は変更しません
- Hard Close 済み（Closing.status=hard_closed）の actual は変更しません
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from sqlalchemy import and_, select

from src.api.deps import SessionLocal
from src.models.enums import ActualStatus, ClosingStatus, InvoiceStatus, PayoutStatus
from src.models.transaction import Actual, Closing, Invoice, InvoiceLine, Payout, PayoutLine
from src.services.audit import AuditService


load_dotenv()


@dataclass
class AdjustmentRow:
    actual_id: str
    applied_price_sales: Decimal | None
    applied_price_outsource: Decimal | None
    reason: str | None


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"Invalid decimal: '{value}'") from exc


def _is_hard_closed(db, actual: Actual) -> bool:
    project_id = actual.assignment.shift_slot.project_id
    stmt = select(Closing).where(
        and_(
            Closing.project_id == project_id,
            Closing.period_key == actual.period_key,
            Closing.status == ClosingStatus.HARD_CLOSED,
        )
    )
    return db.execute(stmt).scalars().first() is not None


def _is_in_issued_invoice_or_payout(db, actual: Actual) -> bool:
    stmt = select(InvoiceLine).where(
        and_(
            InvoiceLine.actual_id == actual.id,
            InvoiceLine.invoice.has(
                Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.CLOSED])
            ),
        )
    )
    if db.execute(stmt).scalars().first() is not None:
        return True

    stmt = select(PayoutLine).where(
        and_(
            PayoutLine.actual_id == actual.id,
            PayoutLine.payout.has(
                Payout.status.in_(
                    [PayoutStatus.APPROVED, PayoutStatus.PAID, PayoutStatus.CLOSED]
                )
            ),
        )
    )
    return db.execute(stmt).scalars().first() is not None


def _load_rows_from_csv(csv_path: Path) -> list[AdjustmentRow]:
    if not csv_path.exists():
        raise FileNotFoundError(str(csv_path))

    rows: list[AdjustmentRow] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"actual_id"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing headers: {sorted(missing)}")

        for line_no, r in enumerate(reader, start=2):
            actual_id = (r.get("actual_id") or "").strip()
            if not actual_id:
                raise ValueError(f"CSV line {line_no}: actual_id is required")

            sales = _parse_decimal(r.get("applied_price_sales"))
            outsource = _parse_decimal(r.get("applied_price_outsource"))
            reason = (r.get("reason") or "").strip() or None

            if sales is None and outsource is None:
                raise ValueError(
                    f"CSV line {line_no}: applied_price_sales or applied_price_outsource is required"
                )

            rows.append(
                AdjustmentRow(
                    actual_id=actual_id,
                    applied_price_sales=sales,
                    applied_price_outsource=outsource,
                    reason=reason,
                )
            )
    return rows


def _apply_adjustment(
    db,
    row: AdjustmentRow,
    *,
    actor: str | None,
    dry_run: bool,
) -> tuple[bool, str]:
    actual = db.get(Actual, row.actual_id)
    if not actual:
        return False, "not_found"

    if actual.status != ActualStatus.ACTIVE:
        return False, f"skipped_status:{actual.status}"

    if _is_hard_closed(db, actual):
        return False, "blocked_hard_closed"

    if _is_in_issued_invoice_or_payout(db, actual):
        return False, "blocked_issued_or_approved"

    before = {
        "applied_price_sales": str(actual.applied_price_sales),
        "applied_price_outsource": str(actual.applied_price_outsource),
    }

    after_sales = actual.applied_price_sales
    after_outsource = actual.applied_price_outsource

    if row.applied_price_sales is not None:
        after_sales = row.applied_price_sales
    if row.applied_price_outsource is not None:
        after_outsource = row.applied_price_outsource

    if dry_run:
        return True, "dry_run"

    actual.applied_price_sales = after_sales
    actual.applied_price_outsource = after_outsource

    AuditService(db).log(
        "actual_applied_price_adjusted",
        target_type="actual",
        target_id=actual.id,
        actor=actor,
        before_value=before,
        after_value={
            "applied_price_sales": str(actual.applied_price_sales),
            "applied_price_outsource": str(actual.applied_price_outsource),
        },
        reason=row.reason,
        extra_metadata={
            "period_key": actual.period_key,
            "work_date": actual.work_date.isoformat() if actual.work_date else None,
            "project_id": actual.assignment.shift_slot.project_id,
        },
    )

    return True, "updated"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Adjust actual.applied_price_sales/outsource with guardrails (default: dry-run)"
    )

    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", type=str, help="CSV file path")
    src.add_argument("--actual-id", type=str, help="Target Actual.id")

    parser.add_argument("--sales", type=_parse_decimal, help="New applied_price_sales")
    parser.add_argument(
        "--outsource", type=_parse_decimal, help="New applied_price_outsource"
    )
    parser.add_argument("--reason", type=str, help="Reason for adjustment")
    parser.add_argument("--actor", type=str, help="Actor identifier (email/user)")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Apply changes (default: dry-run)",
    )

    args = parser.parse_args()

    dry_run = not args.commit

    if args.actual_id:
        if args.sales is None and args.outsource is None:
            parser.error("--sales or --outsource is required when using --actual-id")
        rows = [
            AdjustmentRow(
                actual_id=args.actual_id,
                applied_price_sales=args.sales,
                applied_price_outsource=args.outsource,
                reason=args.reason,
            )
        ]
    else:
        rows = _load_rows_from_csv(Path(args.csv))

    counts: dict[str, int] = {
        "updated": 0,
        "dry_run": 0,
        "not_found": 0,
        "blocked_hard_closed": 0,
        "blocked_issued_or_approved": 0,
        "skipped_other": 0,
    }

    db = SessionLocal()
    try:
        for row in rows:
            ok, status = _apply_adjustment(db, row, actor=args.actor, dry_run=dry_run)
            if not ok:
                if status in counts:
                    counts[status] += 1
                else:
                    counts["skipped_other"] += 1
                print(f"❌ {row.actual_id}: {status}")
                continue

            counts[status] += 1
            prefix = "[DRY RUN]" if status == "dry_run" else "✅"
            print(f"{prefix} {row.actual_id}: {status}")

        if dry_run:
            db.rollback()
        else:
            db.commit()

        print("\nSummary:")
        for k, v in counts.items():
            print(f"  {k}: {v}")

        if dry_run:
            print("\nDry-run only. Re-run with --commit to apply.")

        return 0
    except Exception as exc:
        db.rollback()
        print(f"\n❌ Error: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
