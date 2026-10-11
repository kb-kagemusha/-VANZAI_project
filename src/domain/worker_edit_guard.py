"""通常の稼働者編集で、氏名・連絡先・生年月日・住所の上書きを防ぐ。

比較票はサーバが読んだ7項目から作り、値そのものは票に載せない。
LINE承認の比較票とは用途を分け、入れ替えて使えない。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

WORKER_EDIT_PURPOSE = "worker_edit"
WORKER_EDIT_TTL = timedelta(minutes=60)
GUARDED_FIELDS = (
    "name",
    "furigana",
    "phone",
    "email",
    "birth_date",
    "postal_code",
    "address",
)


class WorkerEditGuardError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _secret() -> bytes:
    key = os.environ.get("WORKER_EDIT_GUARD_KEY") or os.environ.get("JWT_SECRET_KEY")
    if not key:
        raise WorkerEditGuardError("比較票を確認できません。時間をおいてもう一度開いてください。")
    return key.encode("utf-8")


def _blank(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def guarded_values(worker) -> dict[str, str]:
    birth = worker.birth_date.isoformat() if worker.birth_date else ""
    return {
        "name": _blank(worker.name),
        "furigana": _blank(worker.furigana),
        "phone": _blank(worker.phone),
        "email": _blank(worker.email),
        "birth_date": birth,
        "postal_code": _blank(worker.postal_code),
        "address": _blank(worker.address),
    }


def _digest(values: dict[str, str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def issue_worker_edit_guard(worker, editor_id: str, now: datetime | None = None) -> str:
    issued_at = now or datetime.now(timezone.utc)
    body = {
        "v": 1,
        "purpose": WORKER_EDIT_PURPOSE,
        "worker_id": worker.id,
        "editor_id": editor_id,
        "exp": int((issued_at + WORKER_EDIT_TTL).timestamp()),
        "digest": _digest(guarded_values(worker)),
    }
    encoded = _b64(json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_b64(signature)}"


def verify_worker_edit_guard(token: str | None, worker, editor_id: str, now: datetime | None = None) -> None:
    try:
        _verify_worker_edit_guard(token, worker, editor_id, now)
    except WorkerEditGuardError:
        raise
    except Exception as exc:
        raise WorkerEditGuardError("比較票を確認できないため保存しませんでした。編集画面を開き直してください。") from exc


def _verify_worker_edit_guard(token: str | None, worker, editor_id: str, now: datetime | None = None) -> None:
    if not token or "." not in token:
        raise WorkerEditGuardError("比較票がないため保存しませんでした。編集画面を開き直してください。")
    encoded, signature = token.split(".", 1)
    expected = hmac.new(_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    given = _unb64(signature)
    if not hmac.compare_digest(expected, given):
        raise WorkerEditGuardError("比較票を確認できないため保存しませんでした。編集画面を開き直してください。")
    body = json.loads(_unb64(encoded))
    if not isinstance(body, dict):
        raise WorkerEditGuardError("比較票を確認できないため保存しませんでした。編集画面を開き直してください。")
    if body.get("purpose") != WORKER_EDIT_PURPOSE:
        raise WorkerEditGuardError("この比較票では稼働者を保存できません。編集画面を開き直してください。")
    if body.get("worker_id") != worker.id or body.get("editor_id") != editor_id:
        raise WorkerEditGuardError("この比較票では稼働者を保存できません。編集画面を開き直してください。")
    current = datetime.now(timezone.utc) if now is None else now
    if int(body.get("exp") or 0) <= int(current.timestamp()):
        raise WorkerEditGuardError("比較票の期限が切れたため保存しませんでした。最新の内容を読み込んでから、もう一度保存してください。")
    if not hmac.compare_digest(str(body.get("digest") or ""), _digest(guarded_values(worker))):
        raise WorkerEditGuardError("保存する前に稼働者の内容が変わったため、保存しませんでした。最新の内容を読み込んでから、もう一度保存してください。")


def lock_worker_for_edit(db: Session, worker_id: str):
    from src.models.master import Worker

    stmt = select(Worker).where(Worker.id == worker_id)
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()
