#!/usr/bin/env python3
"""App173 の project_id フィールドを削除する。

前提:
- KINTONE_SUBDOMAIN, KINTONE_GUEST_SPACE_ID
- KINTONE_ADMIN_USER, KINTONE_ADMIN_PASSWORD

実行:
  C:/VANZAI_project/.venv/Scripts/python.exe scripts/remove_project_id_from_app173.py
"""

from __future__ import annotations

import base64
import os
import sys

import requests
from dotenv import load_dotenv

APP_ID = 173
FIELD_CODE = "project_id"


def build_base_url() -> str:
    load_dotenv(override=True)
    subdomain = os.getenv("KINTONE_SUBDOMAIN")
    guest_space_id = os.getenv("KINTONE_GUEST_SPACE_ID")
    if not subdomain:
        raise RuntimeError("KINTONE_SUBDOMAIN が未設定です")
    if guest_space_id:
        return f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1"
    return f"https://{subdomain}.cybozu.com/k/v1"


def admin_headers(include_content_type: bool = False) -> dict[str, str]:
    user = os.getenv("KINTONE_ADMIN_USER")
    password = os.getenv("KINTONE_ADMIN_PASSWORD")
    if not user or not password:
        raise RuntimeError("KINTONE_ADMIN_USER / KINTONE_ADMIN_PASSWORD が未設定です")
    auth = base64.b64encode(f"{user}:{password}".encode()).decode()
    headers = {"X-Cybozu-Authorization": auth}
    if include_content_type:
        headers["Content-Type"] = "application/json"
    return headers


def get_fields(base_url: str) -> dict[str, dict]:
    resp = requests.get(
        f"{base_url}/app/form/fields.json",
        headers=admin_headers(False),
        params={"app": str(APP_ID)},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("properties", {})


def delete_field_preview(base_url: str, field_code: str) -> None:
    resp = requests.delete(
        f"{base_url}/preview/app/form/fields.json",
        headers=admin_headers(True),
        json={"app": APP_ID, "fields": [field_code]},
        timeout=60,
    )
    resp.raise_for_status()


def deploy(base_url: str) -> None:
    resp = requests.post(
        f"{base_url}/preview/app/deploy.json",
        headers=admin_headers(True),
        json={"apps": [{"app": APP_ID}]},
        timeout=60,
    )
    resp.raise_for_status()


def main() -> None:
    base_url = build_base_url()

    before = get_fields(base_url)
    if FIELD_CODE not in before:
        print(f"noop: app {APP_ID} に {FIELD_CODE} は存在しません")
        return

    print(f"delete preview: app={APP_ID}, field={FIELD_CODE}")
    delete_field_preview(base_url, FIELD_CODE)
    deploy(base_url)
    print("deploy started")

    after = get_fields(base_url)
    exists = FIELD_CODE in after
    print(f"verify: {FIELD_CODE} exists={exists}")
    if exists:
        raise RuntimeError(f"{FIELD_CODE} の削除確認に失敗しました")

    print("done")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}")
        sys.exit(1)
