"""
push_sender.py — Web Push 送信サービス

VAPID キーを使って Web Push API 経由でブラウザプッシュ通知を送る。
送信失敗した（410 Gone / 404）サブスクリプションは自動削除する。
"""
from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from src.models.master import PushSubscription

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@vanzai-portal.com")


def _send_one(sub: "PushSubscription", payload: dict) -> bool:
    """
    1件のサブスクリプションに push を送る。
    戻り値: True=成功, False=失敗（削除すべき）
    """
    try:
        from pywebpush import webpush, WebPushException  # type: ignore

        webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT},
        )
        return True
    except Exception as exc:  # noqa: BLE001
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (404, 410):
            logger.info("push subscription expired, will delete: %s", sub.endpoint[:60])
            return False
        logger.warning("push send failed (endpoint=%s): %s", sub.endpoint[:60], exc)
        return True  # 一時的な失敗はそのまま保持


def send_push_to_workers(
    db: Session,
    worker_ids: list[str],
    *,
    title: str,
    body: str,
    url: str = "/notices",
    notice_id: str | None = None,
    push_action_type: str | None = None,
) -> None:
    """
    指定 worker_id 一覧に push 通知を送る。
    worker_ids が空の場合は全サブスクリプションに送る（target_type=all）。
    push_action_type:
      - None / "none": アクションボタンなし
      - "ok_ng": 「OKです、了承します」「NGです」ボタン
      - "confirm": 「確認しました」ボタン
    """
    if not VAPID_PRIVATE_KEY:
        logger.debug("VAPID_PRIVATE_KEY not set, skip push")
        return

    from src.models.master import PushSubscription

    q = db.query(PushSubscription)
    if worker_ids:
        q = q.filter(PushSubscription.worker_id.in_(worker_ids))

    subs = q.all()
    if not subs:
        return

    payload: dict = {"title": title, "body": body, "url": url}
    if notice_id:
        payload["notice_id"] = notice_id
    if push_action_type and push_action_type != "none":
        payload["push_action_type"] = push_action_type
    to_delete = []

    for sub in subs:
        ok = _send_one(sub, payload)
        if not ok:
            to_delete.append(sub.id)

    if to_delete:
        db.query(PushSubscription).filter(PushSubscription.id.in_(to_delete)).delete(
            synchronize_session=False
        )
        db.commit()
