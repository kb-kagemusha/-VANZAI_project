"""App171/App173 の legacy（【旧】）フィールドを削除する。

前提:
- KINTONE_SUBDOMAIN, KINTONE_GUEST_SPACE_ID
- KINTONE_ADMIN_USER, KINTONE_ADMIN_PASSWORD

実行:
  C:/VANZAI_project/.venv/Scripts/python.exe scripts/delete_legacy_fields_171_173.py
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
TARGET_APPS = [171, 173]

if not SUBDOMAIN or not ADMIN_USER or not ADMIN_PASSWORD:
    print("❌ 必須環境変数が不足しています")
    sys.exit(1)

if GUEST_SPACE_ID:
    BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/v1"
else:
    BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/v1"


def admin_headers(include_content_type: bool = False) -> dict[str, str]:
    auth = base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASSWORD}".encode()).decode()
    headers = {"X-Cybozu-Authorization": auth}
    if include_content_type:
        headers["Content-Type"] = "application/json"
    return headers


def get_fields(app_id: int) -> dict:
    resp = requests.get(
        f"{BASE_URL}/app/form/fields.json",
        headers=admin_headers(False),
        params={"app": str(app_id)},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("properties", {})


def delete_fields_preview(app_id: int, field_codes: list[str]) -> None:
    if not field_codes:
        return
    resp = requests.delete(
        f"{BASE_URL}/preview/app/form/fields.json",
        headers=admin_headers(True),
        json={"app": app_id, "fields": field_codes},
        timeout=60,
    )
    resp.raise_for_status()


def deploy(app_ids: list[int]) -> None:
    resp = requests.post(
        f"{BASE_URL}/preview/app/deploy.json",
        headers=admin_headers(True),
        json={"apps": [{"app": app_id} for app_id in app_ids]},
        timeout=60,
    )
    resp.raise_for_status()


def legacy_field_codes(properties: dict) -> list[str]:
    result: list[str] = []
    for code, info in properties.items():
        label = str(info.get("label", ""))
        if label.startswith("【旧】"):
            result.append(code)
    return result


def main() -> None:
    print("=" * 72)
    print("App171/App173 legacyフィールド削除")
    print("=" * 72)

    deleted_targets: dict[int, list[str]] = {}

    for app_id in TARGET_APPS:
        props = get_fields(app_id)
        targets = legacy_field_codes(props)
        if not targets:
            print(f"app {app_id}: legacyなし")
            continue

        print(f"app {app_id}: 削除対象 {len(targets)}件")
        for code in targets:
            print(f"  - {code}")

        delete_fields_preview(app_id, targets)
        deleted_targets[app_id] = targets
        print(f"app {app_id}: preview削除完了")

    if not deleted_targets:
        print("変更なし")
        return

    deploy(list(deleted_targets.keys()))
    print("deploy完了")

    print("\n--- 検証 ---")
    for app_id in deleted_targets:
        props = get_fields(app_id)
        remaining = legacy_field_codes(props)
        print(f"app {app_id}: remaining_legacy={len(remaining)}")

    print("=" * 72)
    print("完了")
    print("=" * 72)


if __name__ == "__main__":
    main()
