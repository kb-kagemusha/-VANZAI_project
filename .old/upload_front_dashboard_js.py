#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
front_dashboard.js を kintone App174 にアップロードするスクリプト

手順:
  1. /k/v1/file.json で JS ファイルをアップロード → fileKey 取得
  2. /k/guest/3/v1/preview/app/customize.json で App174 に JS 設定
  3. /k/guest/3/v1/preview/app/deploy.json でデプロイ

実行方法:
  python scripts/upload_front_dashboard_js.py [--dry-run]
"""
import argparse
import base64
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

SUBDOMAIN     = os.getenv("KINTONE_SUBDOMAIN", "xtf5wpxp3gk2")
GUEST_SPACE   = os.getenv("KINTONE_GUEST_SPACE_ID", "3")
ADMIN_USER    = os.getenv("KINTONE_ADMIN_USER", "")
ADMIN_PASS    = os.getenv("KINTONE_ADMIN_PASSWORD", "")
APP_ID        = int(os.getenv("KINTONE_APP_FRONT_DASHBOARD", "174"))
JS_FILE       = project_root / "kintone_app" / "customizations" / "front_dashboard.js"

ADMIN_AUTH = base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASS}".encode()).decode()
HEADERS_AUTH = {
    "X-Cybozu-Authorization": ADMIN_AUTH,
}
BASE_GUEST = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE}/v1"
BASE_V1    = f"https://{SUBDOMAIN}.cybozu.com/k/v1"


def upload_file(js_path: Path) -> str:
    """ファイルをkintoneにアップロードしてfileKeyを取得"""
    with open(js_path, "rb") as f:
        files = {
            "file": (js_path.name, f, "text/javascript"),
        }
        resp = requests.post(
            f"{BASE_V1}/file.json",
            headers=HEADERS_AUTH,
            files=files,
            timeout=30,
        )
    if not resp.ok:
        print(f"❌ ファイルアップロードエラー: {resp.status_code} {resp.text[:300]}")
        sys.exit(1)
    file_key = resp.json().get("fileKey", "")
    print(f"✅ ファイルアップロード成功: fileKey={file_key}")
    return file_key


def set_customize(app_id: int, file_key: str) -> bool:
    """App174のJSカスタマイズをfileKeyで設定（プレビュー）"""
    payload = {
        "app": str(app_id),
        "desktop": {
            "js": [
                {"type": "FILE", "file": {"fileKey": file_key}}
            ],
            "css": [],
        },
        "mobile": {
            "js": [],
            "css": [],
        },
    }
    resp = requests.put(
        f"{BASE_GUEST}/preview/app/customize.json",
        headers={**HEADERS_AUTH, "Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=30,
    )
    if not resp.ok:
        print(f"❌ カスタマイズ設定エラー: {resp.status_code} {resp.text[:300]}")
        return False
    print(f"✅ カスタマイズ設定成功 (preview): {resp.text[:200]}")
    return True


def deploy(app_id: int) -> bool:
    """プレビューを本番にデプロイ"""
    payload = {"apps": [{"app": str(app_id), "revision": "-1"}]}
    resp = requests.post(
        f"{BASE_GUEST}/preview/app/deploy.json",
        headers={**HEADERS_AUTH, "Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=60,
    )
    if not resp.ok:
        print(f"❌ デプロイエラー: {resp.status_code} {resp.text[:300]}")
        return False
    print(f"✅ デプロイ完了: {resp.text[:200]}")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="差分のみ表示（更新しない）")
    args = parser.parse_args()

    if not JS_FILE.exists():
        print(f"❌ JSファイルが見つかりません: {JS_FILE}")
        sys.exit(1)

    size_kb = JS_FILE.stat().st_size / 1024
    print(f"JSファイル: {JS_FILE.name}  ({size_kb:.1f} KB)")
    print(f"アップロード先: App{APP_ID} (ゲストスペース{GUEST_SPACE})")

    if args.dry_run:
        print("[DRY-RUN] 実際の更新はスキップします")
        return

    # Step1: ファイルアップロード
    file_key = upload_file(JS_FILE)

    # Step2: カスタマイズ設定（preview）
    if not set_customize(APP_ID, file_key):
        sys.exit(1)

    # Step3: デプロイ
    if not deploy(APP_ID):
        sys.exit(1)

    print("\n✅ 全ステップ完了！ブラウザのハードリロード（Ctrl+Shift+R）で反映を確認してください。")


if __name__ == "__main__":
    main()
