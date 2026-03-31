"""
[DEPRECATED / 一回限りの移行用]

App165(workers) の 旧「経由先」(group) から
新「経由先」(via_destination) へ値を移行する。

想定は初回移行時のみ。
groupフィールド削除後は通常運用で実行しないこと。

デフォルトは dry-run。

使用例:
    python scripts/migrate_workers_via_destination.py
    python scripts/migrate_workers_via_destination.py --apply
    python scripts/migrate_workers_via_destination.py --apply --overwrite
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv


def normalize_value(old_value: str) -> str | None:
    value = str(old_value or "").strip()
    if not value:
        return None

    if "紹介" in value:
        return "紹介"
    if "下請" in value:
        return "下請け"
    if "VANZAI" in value.upper() or "直接" in value:
        return "VANZAI直接"
    return None


def chunked(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description="workers: group -> via_destination migration")
    parser.add_argument("--apply", action="store_true", help="実際に更新を実行する（未指定時はdry-run）")
    parser.add_argument("--overwrite", action="store_true", help="via_destinationが既にあるレコードも上書き対象にする")
    parser.add_argument("--app-id", type=int, default=int(os.getenv("KINTONE_APP_WORKERS", "165")), help="workers App ID")
    parser.add_argument("--batch-size", type=int, default=100, help="PUT /records.json の更新件数（最大100）")
    args = parser.parse_args()

    subdomain = os.getenv("KINTONE_SUBDOMAIN")
    guest_space_id = os.getenv("KINTONE_GUEST_SPACE_ID")
    token = os.getenv("KINTONE_TOKEN_WORKERS")

    if not subdomain or not token:
        print("❌ KINTONE_SUBDOMAIN / KINTONE_TOKEN_WORKERS が未設定です")
        return 1

    if guest_space_id:
        base_url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1"
    else:
        base_url = f"https://{subdomain}.cybozu.com/k/v1"

    get_headers = {
        "X-Cybozu-API-Token": token,
    }
    put_headers = {
        "X-Cybozu-API-Token": token,
        "Content-Type": "application/json",
    }

    app_id = args.app_id
    dry_run = not args.apply

    print("=" * 70)
    print("workers 経由先移行: group -> via_destination")
    print("=" * 70)
    print(f"app_id         : {app_id}")
    print(f"dry_run        : {dry_run}")
    print(f"overwrite      : {args.overwrite}")
    print(f"guest_space_id : {guest_space_id or '(none)'}")
    print()
    print("※ このスクリプトは一回限りの移行用途です。通常運用では不要です。")
    print()

    # 全件取得（500件ずつ）
    records_url = f"{base_url}/records.json"

    # レコードAPIでフィールド存在チェック（app/form API権限がなくても実行可能）
    probe_query = quote("limit 1")
    probe_url = f"{records_url}?app={app_id}&query={probe_query}"
    probe_resp = requests.get(probe_url, headers=get_headers, timeout=60)
    if probe_resp.status_code >= 400:
        print("❌ via_destination もしくは group フィールドの参照に失敗しました")
        print("   App165に via_destination が追加済みか、APIトークン権限を確認してください")
        print(probe_resp.text)
        return 1

    all_records: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = f"limit 500 offset {offset}"
        encoded_query = quote(query)
        get_url = f"{records_url}?app={app_id}&query={encoded_query}"
        resp = requests.get(get_url, headers=get_headers, timeout=60)
        resp.raise_for_status()
        batch = resp.json().get("records", [])
        if not batch:
            break
        all_records.extend(batch)
        offset += len(batch)

    print(f"総レコード数      : {len(all_records)}")

    # group フィールド削除後は、移行済みとして安全終了
    has_group_field = any("group" in record for record in all_records)
    if not has_group_field:
        print("ℹ️ group フィールドが存在しないため、移行は不要です（削除済み想定）。")
        return 0

    updates: list[dict[str, Any]] = []
    skipped_has_new = 0
    skipped_empty_old = 0
    skipped_unknown = 0
    unknown_samples: list[tuple[str, str]] = []

    for record in all_records:
        record_id = str(record.get("$id", {}).get("value", ""))
        worker_id = str(record.get("worker_id", {}).get("value", ""))
        old_value = str(record.get("group", {}).get("value", "") or "").strip()
        new_value = str(record.get("via_destination", {}).get("value", "") or "").strip()

        if not args.overwrite and new_value:
            skipped_has_new += 1
            continue

        if not old_value:
            skipped_empty_old += 1
            continue

        mapped = normalize_value(old_value)
        if not mapped:
            skipped_unknown += 1
            if len(unknown_samples) < 20:
                unknown_samples.append((worker_id or record_id, old_value))
            continue

        updates.append(
            {
                "id": record_id,
                "record": {
                    "via_destination": {"value": mapped},
                },
            }
        )

    print(f"更新対象件数      : {len(updates)}")
    print(f"skip(viaあり)     : {skipped_has_new}")
    print(f"skip(group空)     : {skipped_empty_old}")
    print(f"skip(変換不可)    : {skipped_unknown}")
    if unknown_samples:
        print("\n変換不可サンプル（先頭20件）:")
        for wid, value in unknown_samples:
            print(f"  - {wid}: {value}")

    if dry_run:
        print("\n✅ dry-run 完了（更新は実行していません）")
        return 0

    if not updates:
        print("\n✅ 更新対象なし（実行不要）")
        return 0

    # 実更新（100件ずつ）
    batch_size = max(1, min(100, args.batch_size))
    update_batches = chunked(updates, batch_size)
    success_count = 0

    for idx, records in enumerate(update_batches, start=1):
        payload = {
            "app": app_id,
            "records": records,
        }
        put_resp = requests.put(records_url, headers=put_headers, json=payload, timeout=60)
        put_resp.raise_for_status()
        success_count += len(records)
        print(f"  [{idx}/{len(update_batches)}] 更新: {len(records)}件（累計 {success_count}件）")

    print(f"\n✅ 移行完了: {success_count}件")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.HTTPError as exc:
        print("\n❌ Kintone APIエラー")
        print(exc)
        if exc.response is not None:
            print(exc.response.text)
        raise SystemExit(1)
    except Exception as exc:
        print("\n❌ 予期せぬエラー")
        print(exc)
        raise SystemExit(1)
