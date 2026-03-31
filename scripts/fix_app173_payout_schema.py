"""App173（payouts）フィールド是正スクリプト。

方針:
- 既存の不適正フィールド型（RADIO_BUTTON/DATETIME等）は破壊的変更せず残す
- 実運用に必要な正規フィールドを追加
- 旧フィールドはラベルを `【旧】...` に変更し誤操作を防止
- preview更新 -> deploy で本番反映

使用方法:
    C:/VANZAI_project/.venv/Scripts/python.exe scripts/fix_app173_payout_schema.py
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv(override=True)

SUBDOMAIN = os.getenv("KINTONE_SUBDOMAIN")
GUEST_SPACE_ID = os.getenv("KINTONE_GUEST_SPACE_ID")
ADMIN_USER = os.getenv("KINTONE_ADMIN_USER")
ADMIN_PASSWORD = os.getenv("KINTONE_ADMIN_PASSWORD")
APP_ID = int(os.getenv("KINTONE_APP_PAYOUTS", "173"))

if not SUBDOMAIN or not ADMIN_USER or not ADMIN_PASSWORD:
    print("❌ 必須環境変数が不足しています (KINTONE_SUBDOMAIN / KINTONE_ADMIN_USER / KINTONE_ADMIN_PASSWORD)")
    sys.exit(1)

if GUEST_SPACE_ID:
    BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/v1"
else:
    BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/v1"


def admin_headers(include_content_type: bool = True) -> dict[str, str]:
    auth = base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASSWORD}".encode()).decode()
    headers = {"X-Cybozu-Authorization": auth}
    if include_content_type:
        headers["Content-Type"] = "application/json"
    return headers


def get_fields() -> dict:
    url = f"{BASE_URL}/app/form/fields.json"
    resp = requests.get(url, headers=admin_headers(include_content_type=False), params={"app": APP_ID}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("properties", {})


def add_preview(properties: dict) -> None:
    if not properties:
        print("ℹ️ 更新対象なし")
        return
    url = f"{BASE_URL}/preview/app/form/fields.json"
    payload = {"app": APP_ID, "properties": properties}
    resp = requests.post(url, headers=admin_headers(), json=payload, timeout=60)
    resp.raise_for_status()


def update_preview(properties: dict) -> None:
    if not properties:
        print("ℹ️ 更新対象なし")
        return
    url = f"{BASE_URL}/preview/app/form/fields.json"
    payload = {"app": APP_ID, "properties": properties}
    resp = requests.put(url, headers=admin_headers(), json=payload, timeout=60)
    resp.raise_for_status()


def deploy() -> None:
    url = f"{BASE_URL}/preview/app/deploy.json"
    payload = {"apps": [{"app": APP_ID}]}
    resp = requests.post(url, headers=admin_headers(), json=payload, timeout=60)
    resp.raise_for_status()


NEW_FIELDS: dict[str, dict] = {
    "payout_id": {
        "type": "SINGLE_LINE_TEXT",
        "code": "payout_id",
        "label": "支払明細ID",
    },
    "worker_id": {
        "type": "SINGLE_LINE_TEXT",
        "code": "worker_id",
        "label": "稼働者ID",
    },
    "supplier_id": {
        "type": "SINGLE_LINE_TEXT",
        "code": "supplier_id",
        "label": "紹介者ID",
    },
    "project_id": {
        "type": "SINGLE_LINE_TEXT",
        "code": "project_id",
        "label": "案件ID",
    },
    "period_key": {
        "type": "SINGLE_LINE_TEXT",
        "code": "period_key",
        "label": "対象月(YYYYMM)",
    },
    "payment_date": {
        "type": "DATE",
        "code": "payment_date",
        "label": "支払日",
    },
    "status": {
        "type": "DROP_DOWN",
        "code": "status",
        "label": "ステータス",
        "options": {
            "preparing": {"label": "preparing", "index": "0"},
            "approved": {"label": "approved", "index": "1"},
            "paid": {"label": "paid", "index": "2"},
            "closed": {"label": "closed", "index": "3"},
        },
        "defaultValue": "preparing",
    },
    "version": {
        "type": "NUMBER",
        "code": "version",
        "label": "版",
        "defaultValue": "1",
    },
    "parent_payout_id": {
        "type": "SINGLE_LINE_TEXT",
        "code": "parent_payout_id",
        "label": "親支払明細ID",
    },
    "total_amount": {
        "type": "NUMBER",
        "code": "total_amount",
        "label": "合計金額",
    },
    "approved_at": {
        "type": "DATETIME",
        "code": "approved_at",
        "label": "承認日時",
    },
    "paid_at": {
        "type": "DATETIME",
        "code": "paid_at",
        "label": "支払完了日時",
    },
    "closed_at": {
        "type": "DATE",
        "code": "closed_at",
        "label": "締め日",
    },
    "notes": {
        "type": "MULTI_LINE_TEXT",
        "code": "notes",
        "label": "備考",
    },
}

LEGACY_LABELS: dict[str, str] = {
    "ラジオボタン": "【旧】支払明細ID",
    "ラジオボタン_0": "【旧】稼働者ID",
    "ラジオボタン_1": "【旧】案件ID",
    "ラジオボタン_2": "【旧】ステータス",
    "ラジオボタン_3": "【旧】備考",
    "文字列__1行_": "【旧】親支払明細ID",
    "文字列__1行__0": "【旧】支払完了日時",
    "数値": "【旧】対象月(YYYYMM)",
    "数値_0": "【旧】版",
    "数値_1": "【旧】合計金額",
    "日付": "【旧】支払日",
    "日時": "【旧】承認日時",
    "日時_0": "【旧】締め日時",
    "日時_1": "【旧】作成日時",
    "日時_2": "【旧】更新日時",
}


def main() -> None:
    print("=" * 64)
    print(f"App173 フィールド是正を開始 (app={APP_ID})")
    print("=" * 64)

    current = get_fields()
    print(f"現在フィールド数: {len(current)}")

    add_payload: dict[str, dict] = {}
    for code, definition in NEW_FIELDS.items():
        if code not in current:
            add_payload[code] = definition

    legacy_update_payload: dict[str, dict] = {}
    for code, label in LEGACY_LABELS.items():
        field = current.get(code)
        if not field:
            continue
        if field.get("label") == label:
            continue
        legacy_update_payload[code] = {
            "type": field.get("type"),
            "code": code,
            "label": label,
        }

    if add_payload:
        print(f"追加: {', '.join(add_payload.keys())}")
        add_preview(add_payload)
    else:
        print("追加対象なし")

    if legacy_update_payload:
        print(f"旧ラベル化: {', '.join(legacy_update_payload.keys())}")
        update_preview(legacy_update_payload)
    else:
        print("旧ラベル化対象なし")

    if add_payload or legacy_update_payload:
        deploy()
        print("✅ deploy完了")
    else:
        print("ℹ️ 変更なし")

    latest = get_fields()
    print("\n--- 確認（主要フィールド）---")
    for key in [
        "payout_id",
        "worker_id",
        "project_id",
        "period_key",
        "payment_date",
        "status",
        "total_amount",
        "closed_at",
        "notes",
        "ラジオボタン",
        "ラジオボタン_0",
        "日時_0",
    ]:
        if key in latest:
            props = latest[key]
            print(f"{key}: {props.get('type')} / {props.get('label')}")

    print("=" * 64)
    print("完了")
    print("=" * 64)


if __name__ == "__main__":
    main()
