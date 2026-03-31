"""App171 の旧由来フィールドを物理削除する。"""

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
APP_ID = 171

OBSOLETE_CODES = [
    "文字列__1行_",
    "日付",
    "数値",
    "数値_0",
    "数値_1",
    "数値_2",
    "数値_3",
    "文字列__1行__0",
    "日時",
    "日時_0",
    "日時_1",
]

if not SUBDOMAIN or not ADMIN_USER or not ADMIN_PASSWORD:
    print("❌ 必須環境変数が不足しています")
    sys.exit(1)

if GUEST_SPACE_ID:
    BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE_ID}/v1"
else:
    BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/v1"


def headers(include_content_type: bool = False) -> dict[str, str]:
    auth = base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASSWORD}".encode()).decode()
    result = {"X-Cybozu-Authorization": auth}
    if include_content_type:
        result["Content-Type"] = "application/json"
    return result


def get_fields() -> dict:
    r = requests.get(
        f"{BASE_URL}/app/form/fields.json",
        headers=headers(False),
        params={"app": str(APP_ID)},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("properties", {})


def delete_preview(codes: list[str]) -> None:
    if not codes:
        return
    r = requests.delete(
        f"{BASE_URL}/preview/app/form/fields.json",
        headers=headers(True),
        json={"app": APP_ID, "fields": codes},
        timeout=60,
    )
    r.raise_for_status()


def deploy() -> None:
    r = requests.post(
        f"{BASE_URL}/preview/app/deploy.json",
        headers=headers(True),
        json={"apps": [{"app": APP_ID}]},
        timeout=60,
    )
    r.raise_for_status()


def main() -> None:
    print("=" * 64)
    print("App171 旧由来フィールド削除")
    print("=" * 64)

    props = get_fields()
    targets = [code for code in OBSOLETE_CODES if code in props]

    if not targets:
        print("削除対象なし")
        return

    print(f"削除対象: {len(targets)}")
    for code in targets:
        info = props[code]
        print(f"- {code} ({info.get('type')} / {info.get('label')})")

    delete_preview(targets)
    print("preview削除完了")
    deploy()
    print("deploy完了")

    latest = get_fields()
    remaining = [code for code in OBSOLETE_CODES if code in latest]
    print(f"remaining obsolete: {len(remaining)}")
    if remaining:
        print(remaining)


if __name__ == "__main__":
    main()
