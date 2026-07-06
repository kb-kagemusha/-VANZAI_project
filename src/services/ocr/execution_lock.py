"""PostgreSQL advisory lock (with sqlite fallback) for global OCR execution."""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session

OCR_GLOBAL_LOCK_KEY = 73482901
_thread_lock = threading.Lock()


def _dialect_name(session: Session) -> str:
    bind = session.get_bind()
    return bind.dialect.name if bind is not None else "sqlite"


@contextmanager
def ocr_execution_lock(session: Session) -> Iterator[None]:
    """Blocking global OCR lock."""
    if _dialect_name(session) == "postgresql":
        session.execute(text("SELECT pg_advisory_lock(:key)"), {"key": OCR_GLOBAL_LOCK_KEY})
        try:
            yield
        finally:
            session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": OCR_GLOBAL_LOCK_KEY})
    else:
        with _thread_lock:
            yield


@contextmanager
def try_ocr_execution_lock(session: Session, *, timeout_seconds: float = 5.0) -> Iterator[bool]:
    """Try to acquire OCR lock within timeout. Yields whether lock was acquired."""
    if _dialect_name(session) == "postgresql":
        deadline = time.monotonic() + timeout_seconds
        acquired = False
        try:
            while time.monotonic() < deadline:
                acquired = bool(
                    session.execute(
                        text("SELECT pg_try_advisory_lock(:key)"),
                        {"key": OCR_GLOBAL_LOCK_KEY},
                    ).scalar()
                )
                if acquired:
                    break
                time.sleep(0.05)
            yield acquired
        finally:
            if acquired:
                session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": OCR_GLOBAL_LOCK_KEY})
    else:
        acquired = _thread_lock.acquire(timeout=timeout_seconds)
        try:
            yield acquired
        finally:
            if acquired:
                _thread_lock.release()
