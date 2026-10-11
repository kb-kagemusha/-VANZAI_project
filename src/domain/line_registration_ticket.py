"""LINE承認の比較票。通常編集の比較票とは用途が違い、入れ替えられない。

票に載せるのは識別子と要約だけで、項目の値そのものは載せない。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone

from src.domain.worker_edit_guard import GUARDED_FIELDS

LINE_REVIEW_PURPOSE = "line_registration_approval"
LINE_REVIEW_TTL = timedelta(minutes=60)
RELOAD_MESSAGE = "表示中の内容が変わりました。最新の内容を読み込んでから、もう一度審査してください。"


class LineReviewTicketError(Exception):
    def __init__(self, message: str = RELOAD_MESSAGE) -> None:
        super().__init__(message)
        self.message = message


def _secret() -> bytes:
    key = os.environ.get("WORKER_EDIT_GUARD_KEY") or os.environ.get("JWT_SECRET_KEY")
    if not key:
        raise LineReviewTicketError("比較票を確認できません。時間をおいてもう一度開いてください。")
    return key.encode("utf-8")


def _digest(values: dict[str, str]) -> str:
    payload = json.dumps(
        {field: values.get(field, "") for field in GUARDED_FIELDS},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def issue_line_review_ticket(
    *,
    request_id: str,
    reviewer_id: str,
    mode: str,
    worker_id: str | None,
    link_id: str | None,
    before: dict[str, str],
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(timezone.utc)
    body = {
        "v": 1,
        "purpose": LINE_REVIEW_PURPOSE,
        "request_id": request_id,
        "reviewer_id": reviewer_id,
        "mode": mode,
        "worker_id": worker_id or "",
        "link_id": link_id or "",
        "fields": list(GUARDED_FIELDS),
        "exp": int((issued_at + LINE_REVIEW_TTL).timestamp()),
        "digest": _digest(before),
    }
    encoded = _b64(json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_b64(signature)}"


def verify_line_review_ticket(
    token: str | None,
    *,
    request_id: str,
    reviewer_id: str,
    mode: str,
    worker_id: str | None,
    link_id: str | None,
    before: dict[str, str],
    now: datetime | None = None,
) -> None:
    try:
        _verify(
            token,
            request_id=request_id,
            reviewer_id=reviewer_id,
            mode=mode,
            worker_id=worker_id or "",
            link_id=link_id or "",
            before=before,
            now=now or datetime.now(timezone.utc),
        )
    except LineReviewTicketError:
        raise
    except Exception as exc:
        raise LineReviewTicketError() from exc


def _verify(
    token: str | None,
    *,
    request_id: str,
    reviewer_id: str,
    mode: str,
    worker_id: str,
    link_id: str,
    before: dict[str, str],
    now: datetime,
) -> None:
    if not token or "." not in token:
        raise LineReviewTicketError()
    encoded, signature = token.split(".", 1)
    expected = hmac.new(_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _unb64(signature)):
        raise LineReviewTicketError()
    body = json.loads(_unb64(encoded))
    if not isinstance(body, dict) or body.get("purpose") != LINE_REVIEW_PURPOSE:
        raise LineReviewTicketError()
    if body.get("fields") != list(GUARDED_FIELDS):
        raise LineReviewTicketError()
    if (
        body.get("request_id") != request_id
        or body.get("reviewer_id") != reviewer_id
        or body.get("mode") != mode
        or body.get("worker_id") != worker_id
        or body.get("link_id") != link_id
    ):
        raise LineReviewTicketError()
    if int(body.get("exp") or 0) <= int(now.timestamp()):
        raise LineReviewTicketError()
    if not hmac.compare_digest(str(body.get("digest") or ""), _digest(before)):
        raise LineReviewTicketError()
