"""起床の監視を1回動かす（毎分、cron から 02_app_deploy.sh --wake-monitor 経由で呼ぶ。0.54.0、DEC-126）。"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import src.models  # noqa: F401,E402  register foreign keys
import src.models.line_daily  # noqa: F401,E402
import src.models.operator_registration  # noqa: F401,E402
from src.api.deps import SessionLocal  # noqa: E402
from src.services import worker_schedule as ws  # noqa: E402
from src.services.wake_monitor import WakeMonitorService  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        counts = WakeMonitorService(db).run()
        db.commit()
        if any(value for value in counts.values() if isinstance(value, int)):
            print(json.dumps({"at": ws.now_utc().isoformat(), **counts}, ensure_ascii=False))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
