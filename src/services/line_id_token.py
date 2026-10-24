"""LINEのIDトークンの検証（登録・稼働者機能で共通）。

登録の受付が有効かどうかとは切り離す（統合計画 R-06）。登録を止めても稼働者機能の本人確認は動く。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

VERIFY_URL = "https://api.line.me/oauth2/v2.1/verify"
LINE_ID_TOKEN_EXPIRED = "LINEのログイン期限が切れました。LINEでもう一度開き直してください。この画面の入力は、開き直すと残りません。"


class LineIdTokenError(Exception):
    def __init__(self, message: str = "本人確認に失敗しました。"):
        super().__init__(message)
        self.message = message


def line_verify_error_message(body: str) -> str:
    lowered = body.lower()
    if "expir" in lowered:
        return LINE_ID_TOKEN_EXPIRED
    return "本人確認に失敗しました。"


def assert_line_id_token_usable(payload: dict, channel_id: str, now: datetime) -> str:
    if not isinstance(payload, dict) or payload.get("aud") != channel_id:
        raise LineIdTokenError()
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise LineIdTokenError()
    exp = payload.get("exp")
    if isinstance(exp, bool) or not isinstance(exp, (int, float)) or int(exp) <= int(now.timestamp()):
        raise LineIdTokenError(LINE_ID_TOKEN_EXPIRED)
    return subject.strip()


def verify_id_token(id_token: str, channel_id: str) -> str:
    """LINEの検証APIでIDトークンを確かめ、本人のLINEユーザーIDを返す。"""
    if not channel_id or not isinstance(id_token, str) or not id_token.strip():
        raise LineIdTokenError()
    body = urllib.parse.urlencode({"id_token": id_token, "client_id": channel_id}).encode("utf-8")
    request = urllib.request.Request(VERIFY_URL, data=body, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        raise LineIdTokenError(line_verify_error_message(detail)) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeError) as exc:
        raise LineIdTokenError() from exc
    return assert_line_id_token_usable(payload, channel_id, datetime.now(timezone.utc))
