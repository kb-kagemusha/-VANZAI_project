"""期限を過ぎて返事が無い発注依頼へ、案内を1回送る。"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.api.deps import SessionLocal
from src.services.line_order import LineOrderService


def main() -> None:
    db = SessionLocal()
    try:
        count = LineOrderService(db).send_due_reminders()
        db.commit()
        print(f"reminded {count}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
