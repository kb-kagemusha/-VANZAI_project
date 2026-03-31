#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLiteのworkersテーブル（ULID→name）をKintoneのDROP_DOWNオプションlabelに反映する

対象アプリ:
  - App168 (actuals)   の worker_id DROP_DOWN
  - App158 (assignments) の worker_id DROP_DOWN

実行方法:
  python scripts/sync_worker_labels_to_kintone.py [--dry-run]

--dry-run: 実際の更新は行わず差分のみ表示
"""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
load_dotenv()

SUBDOMAIN     = os.getenv("KINTONE_SUBDOMAIN", "")
GUEST_SPACE   = os.getenv("KINTONE_GUEST_SPACE_ID", "3")
TOKEN_ACTUALS = os.getenv("KINTONE_TOKEN_ACTUALS", "")
TOKEN_ASSIGN  = os.getenv("KINTONE_TOKEN_ASSIGNMENTS", "")
ADMIN_USER    = os.getenv("KINTONE_ADMIN_USER", "")
ADMIN_PASS    = os.getenv("KINTONE_ADMIN_PASSWORD", "")
DB_PATH       = project_root / "vanzai.db"

BASE_URL = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE}/v1"

# フォーム設定変更にはX-Cybozu-Authorizationが必要
import base64
ADMIN_AUTH = base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASS}".encode()).decode()


def get_worker_name_map() -> dict:
    """SQLiteのworkersテーブルからULID→name マッピングを取得"""
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM workers WHERE deleted_at IS NULL")
    rows = {r[0]: r[1] for r in cur.fetchall()}
    conn.close()
    return rows


def get_current_options(app_id: int, field_code: str, token: str) -> dict:
    """kintoneのDROP_DOWNフィールドの現在のoptionsを取得"""
    resp = requests.get(
        f"{BASE_URL}/app/form/fields.json",
        headers={"X-Cybozu-API-Token": token},
        params={"app": app_id},
        timeout=30,
    )
    resp.raise_for_status()
    props = resp.json().get("properties", {})
    field = props.get(field_code, {})
    return field.get("options", {})


def build_new_options(current_options: dict, worker_name_map: dict) -> tuple[dict, list]:
    """
    現在のoptionsにworker_name_mapを反映した新しいoptionsを構築する。
    - DBに存在するULIDキーはlabelを氏名に更新（kintoneに未登録なら新規追加）
    - DBに存在しないキーはcurrent_optionsのまま保持
    Returns: (new_options, changes_list)
    """
    new_options = {}
    changes = []

    # まず現在のoptionsを引き継ぐ（非ULIDキーも保持）
    existing_keys = set()
    for key, opt_info in current_options.items():
        current_label = opt_info.get("label", key)
        new_label = worker_name_map.get(key, current_label)  # DB登録済みなら氏名で上書き
        new_options[key] = {
            "label": new_label,
            "index": opt_info.get("index", "0"),
        }
        if new_label != current_label:
            changes.append((key, current_label, new_label))
        existing_keys.add(key)

    # DBにあるがkintoneのoptionsに存在しないULIDを追加（新規登録）
    idx = len(new_options)
    for ulid, name in worker_name_map.items():
        if ulid not in existing_keys:
            new_options[ulid] = {"label": name, "index": str(idx)}
            changes.append((ulid, "(未登録)", name))
            idx += 1

    return new_options, changes


def update_dropdown_options(app_id: int, field_code: str, token: str, new_options: dict, dry_run: bool) -> bool:
    """kintoneのDROP_DOWNフィールドのoptionsを更新"""
    payload = {
        "app": app_id,
        "properties": {
            field_code: {
                "type": "DROP_DOWN",
                "options": new_options,
            }
        },
    }
    if dry_run:
        print(f"  [DRY-RUN] App{app_id}.{field_code} options更新をスキップ")
        return True

    headers = {
        "X-Cybozu-Authorization": ADMIN_AUTH,
        "Content-Type": "application/json",
    }
    # ゲストスペース内のアプリはpreviewエンドポイントを使用
    base_guest = f"https://{SUBDOMAIN}.cybozu.com/k/guest/{GUEST_SPACE}/v1"

    resp = requests.put(
        f"{base_guest}/preview/app/form/fields.json",
        headers=headers,
        data=json.dumps(payload, ensure_ascii=False),
        timeout=30,
    )
    if not resp.ok:
        print(f"  ❌ フィールド更新エラー: {resp.status_code} {resp.text[:200]}")
        return False

    # プレビューを本番に公開
    deploy_payload = {"apps": [{"app": str(app_id), "revision": "-1"}]}
    deploy_resp = requests.post(
        f"{base_guest}/preview/app/deploy.json",
        headers=headers,
        data=json.dumps(deploy_payload),
        timeout=30,
    )
    if not deploy_resp.ok:
        print(f"  ❌ デプロイエラー: {deploy_resp.status_code} {deploy_resp.text[:200]}")
        return False

    print(f"  ✅ App{app_id}.{field_code} 更新・デプロイ完了")
    return True


def process_app(app_id: int, field_code: str, token: str, worker_name_map: dict, dry_run: bool):
    print(f"\n========== App{app_id} フィールド:{field_code} ==========")
    current_opts = get_current_options(app_id, field_code, token)
    print(f"  現在のoptions件数: {len(current_opts)}")

    new_opts, changes = build_new_options(current_opts, worker_name_map)

    if not changes:
        print("  変更なし（全ラベルは既に正しい）")
        return

    print(f"  更新対象: {len(changes)}件")
    for key, old_label, new_label in changes:
        print(f"    {key}: '{old_label}' → '{new_label}'")

    update_dropdown_options(app_id, field_code, token, new_opts, dry_run)


def main():
    parser = argparse.ArgumentParser(description="Sync worker labels to Kintone DROP_DOWN options")
    parser.add_argument("--dry-run", action="store_true", help="差分表示のみ（更新しない）")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"❌ DBファイルが見つかりません: {DB_PATH}")
        sys.exit(1)

    worker_name_map = get_worker_name_map()
    print(f"SQLite workers: {len(worker_name_map)}件")
    for k, v in sorted(worker_name_map.items()):
        print(f"  {k} -> {v}")

    # App168 (actuals) の worker_id
    process_app(168, "worker_id", TOKEN_ACTUALS, worker_name_map, args.dry_run)
    # App158 (assignments) の worker_id
    process_app(158, "worker_id", TOKEN_ASSIGN, worker_name_map, args.dry_run)

    if not args.dry_run:
        print("\n✅ 完了！kintoneのlabel更新後はブラウザをハードリロードしてください。")
    else:
        print("\n（--dry-run モードのため実際の更新は行いませんでした）")


if __name__ == "__main__":
    main()
