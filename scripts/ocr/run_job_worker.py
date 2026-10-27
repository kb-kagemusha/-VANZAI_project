#!/usr/bin/env python3
"""OCR parse job worker — processes pending ocr_parse_jobs."""
from __future__ import annotations

import os
import sys
import time

# Ensure project root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.api.deps import SessionLocal
from src.services.ocr.job_worker import process_one_pending_job


def main() -> None:
    sleep_seconds = float(os.getenv("OCR_WORKER_SLEEP_SECONDS", "3"))
    while True:
        session = SessionLocal()
        try:
            processed = process_one_pending_job(session)
            if not processed:
                session.close()
                time.sleep(sleep_seconds)
        except KeyboardInterrupt:
            session.close()
            break
        except Exception:
            session.rollback()
            session.close()
            time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
