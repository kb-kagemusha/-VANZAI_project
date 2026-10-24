"""公式LINEの稼働者登録入口。未設定のときは無効。"""
from __future__ import annotations

import os

REGISTRATION_KEYWORD = "登録"


def is_registration_keyword(text: str) -> bool:
    return text.strip() == REGISTRATION_KEYWORD


def registration_entry_enabled() -> bool:
    return os.getenv("LINE_WORKER_REGISTRATION_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def registration_liff_id() -> str:
    return os.getenv("LINE_LIFF_ID", "").strip()


def registration_login_channel_id() -> str:
    return os.getenv("LINE_LOGIN_CHANNEL_ID", "").strip()


def registration_entry_ready() -> bool:
    return bool(registration_entry_enabled() and registration_liff_id() and registration_login_channel_id())


def registration_button_messages() -> list[dict] | None:
    if not registration_entry_ready():
        return None
    liff_id = registration_liff_id()
    return [
        {
            "type": "template",
            "altText": "稼働者登録",
            "template": {
                "type": "buttons",
                "text": "稼働者情報の登録は、このボタンから入力します。",
                "actions": [
                    {
                        "type": "uri",
                        "label": "登録する",
                        "uri": f"https://liff.line.me/{liff_id}",
                    }
                ],
            },
        }
    ]
