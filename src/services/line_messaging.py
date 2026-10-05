"""LINE Messaging API の署名確認と送信。トークンはログに出さない。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


PUSH_URL = "https://api.line.me/v2/bot/message/push"
REPLY_URL = "https://api.line.me/v2/bot/message/reply"
PROFILE_URL = "https://api.line.me/v2/bot/profile/{user_id}"


@dataclass(frozen=True)
class LineSettings:
    channel_id: str
    channel_secret: str
    access_token: str
    public_api_base: str

    @property
    def configured(self) -> bool:
        return bool(self.channel_id and self.channel_secret and self.access_token)


def line_settings() -> LineSettings:
    return LineSettings(
        channel_id=os.getenv("LINE_CHANNEL_ID", "").strip(),
        channel_secret=os.getenv("LINE_CHANNEL_SECRET", "").strip(),
        access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip(),
        public_api_base=os.getenv("LINE_PUBLIC_API_BASE", "https://api.vanzai-portal.com").strip(),
    )


def verify_line_signature(body: bytes, signature: str, channel_secret: str) -> bool:
    if not channel_secret or not signature:
        return False
    digest = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    candidate = signature.strip()
    if len(expected) != len(candidate):
        return False
    return hmac.compare_digest(expected, candidate)


@dataclass(frozen=True)
class LineCallResult:
    status: int
    message: str
    request_id: str | None


class LineNotConfigured(Exception):
    pass


class LineMessagingClient:
    def push_messages(self, to: str, messages: list[dict]) -> LineCallResult:
        return self._post(PUSH_URL, {"to": to, "messages": messages})

    def reply_text(self, reply_token: str, text: str) -> None:
        if not reply_token:
            return
        self._post(REPLY_URL, {"replyToken": reply_token, "messages": [{"type": "text", "text": text}]})

    def profile_name(self, user_id: str) -> str | None:
        settings = line_settings()
        if not settings.access_token or not user_id:
            return None
        url = PROFILE_URL.format(user_id=urllib.request.quote(user_id))
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {settings.access_token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8") or "{}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeError):
            return None
        name = payload.get("displayName")
        if not isinstance(name, str):
            return None
        cleaned = name.strip()
        return cleaned[:200] or None

    def _post(self, url: str, payload: dict) -> LineCallResult:
        settings = line_settings()
        if not settings.access_token:
            raise LineNotConfigured()
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                request_id = response.headers.get("X-Line-Request-Id")
                return LineCallResult(response.status, "", request_id)
        except urllib.error.HTTPError as exc:
            message = _error_message(exc.read())
            return LineCallResult(exc.code, message, None)
        except (urllib.error.URLError, TimeoutError):
            return LineCallResult(0, "LINEへの接続に失敗しました", None)


def build_line_client() -> LineMessagingClient:
    return LineMessagingClient()


def _error_message(raw: bytes) -> str:
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeError):
        return "LINEが送信を拒否しました"
    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, str) or not message.strip():
        return "LINEが送信を拒否しました"
    return message.strip()[:200]
