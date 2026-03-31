#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import json
import os
import argparse
from datetime import date

import requests
from dotenv import load_dotenv


APP_WORKERS = 165
APP_ACTUALS = 168
APP_PAYOUTS = 173


def kintone_base_and_headers():
    load_dotenv()
    sub = os.getenv("KINTONE_SUBDOMAIN")
    guest = os.getenv("KINTONE_GUEST_SPACE_ID")
    user = os.getenv("KINTONE_ADMIN_USER")
    password = os.getenv("KINTONE_ADMIN_PASSWORD")
    if not (sub and guest and user and password):
        raise RuntimeError("KINTONE_* env is missing")
    auth = base64.b64encode(f"{user}:{password}".encode()).decode()
    base = f"https://{sub}.cybozu.com/k/guest/{guest}/v1"
    headers = {"X-Cybozu-Authorization": auth}
    return base, headers


def get_fields(base, headers, app_id):
    resp = requests.get(
        f"{base}/app/form/fields.json",
        headers=headers,
        params={"app": str(app_id)},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("properties", {})


def get_records(base, headers, app_id, query, fields=None):
    params = {"app": str(app_id), "query": query}
    if fields:
        for i, f in enumerate(fields):
            params[f"fields[{i}]"] = f
    resp = requests.get(f"{base}/records.json", headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("records", [])


def add_record(base, headers, app_id, record):
    resp = requests.post(
        f"{base}/record.json",
        headers={**headers, "Content-Type": "application/json"},
        data=json.dumps({"app": str(app_id), "record": record}, ensure_ascii=False),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("id")


def set_if_exists(record, props, code, value):
    if code in props and value is not None:
        record[code] = {"value": value}


def parse_args():
    parser = argparse.ArgumentParser(description="Create dummy worker/actual/payout for payout testing")
    parser.add_argument("--via", default="VANZAI直接", choices=["VANZAI直接", "紹介", "下請け"], help="経由先")
    parser.add_argument("--last-name", default="ダミー", help="姓")
    parser.add_argument("--first-name", default="稼働者", help="名")
    parser.add_argument("--amount", type=int, default=10000, help="支払明細の金額")
    return parser.parse_args()


def main():
    args = parse_args()
    base, headers = kintone_base_and_headers()

    worker_props = get_fields(base, headers, APP_WORKERS)
    actual_props = get_fields(base, headers, APP_ACTUALS)
    payout_props = get_fields(base, headers, APP_PAYOUTS)

    worker_dropdown_opts = list((actual_props.get("worker_id", {}).get("options") or {}).keys())
    if not worker_dropdown_opts:
        raise RuntimeError("App168 worker_id の選択肢が空です。先に選択肢を設定してください。")

    existing_workers = get_records(base, headers, APP_WORKERS, "order by $id asc limit 500", ["worker_id"])
    existing_ids = {
        str((row.get("worker_id") or {}).get("value") or "").strip()
        for row in existing_workers
    }

    candidate_worker_id = ""
    for opt in worker_dropdown_opts:
        opt_val = str(opt).strip()
        if opt_val and opt_val not in existing_ids:
            candidate_worker_id = opt_val
            break

    if not candidate_worker_id:
        raise RuntimeError(
            "App168 worker_id の選択肢は全て既存稼働者IDです。"
            "新規ダミー作成のため、App168 worker_id 選択肢に未使用IDを1件追加してください。"
        )

    today = date.today()
    period_key = f"{today.year}{str(today.month).zfill(2)}"

    worker_record = {}
    set_if_exists(worker_record, worker_props, "worker_id", candidate_worker_id)
    set_if_exists(worker_record, worker_props, "last_name", args.last_name)
    set_if_exists(worker_record, worker_props, "first_name", args.first_name)
    set_if_exists(worker_record, worker_props, "is_active", "有効")
    set_if_exists(worker_record, worker_props, "sex", "男性")
    set_if_exists(worker_record, worker_props, "full_part", "スポット")
    set_if_exists(worker_record, worker_props, "via_destination", args.via)
    set_if_exists(worker_record, worker_props, "phone", "09000000000")
    set_if_exists(worker_record, worker_props, "email", f"dummy.{candidate_worker_id.lower()}@example.com")
    set_if_exists(worker_record, worker_props, "memos", f"支払明細発行テスト用のダミー稼働者（{args.via}）")

    worker_id = add_record(base, headers, APP_WORKERS, worker_record)

    project_opts = list((actual_props.get("project_id", {}).get("options") or {}).keys())
    role_opts = list((actual_props.get("role_id", {}).get("options") or {}).keys())
    if not project_opts or not role_opts:
        raise RuntimeError("App168 の project_id / role_id 選択肢が不足しています。")

    actual_record = {}
    set_if_exists(actual_record, actual_props, "worker_id", candidate_worker_id)
    set_if_exists(actual_record, actual_props, "work_date", today.isoformat())
    set_if_exists(actual_record, actual_props, "period_key", period_key)
    set_if_exists(actual_record, actual_props, "worked_start_time", "09:00")
    set_if_exists(actual_record, actual_props, "worked_end_time", "18:00")
    set_if_exists(actual_record, actual_props, "assignment_status_hint", "confirmed")
    set_if_exists(actual_record, actual_props, "memo", "テスト用")
    set_if_exists(actual_record, actual_props, "project_id", project_opts[0])
    set_if_exists(actual_record, actual_props, "role_id", role_opts[0])
    set_if_exists(actual_record, actual_props, "actual_status", "active")

    actual_id = add_record(base, headers, APP_ACTUALS, actual_record)

    payout_record = {}
    set_if_exists(payout_record, payout_props, "worker_id", candidate_worker_id)
    set_if_exists(payout_record, payout_props, "period_key", period_key)
    set_if_exists(payout_record, payout_props, "payout_id", f"PD-{period_key}-{candidate_worker_id}")
    set_if_exists(payout_record, payout_props, "total_amount", args.amount)
    set_if_exists(payout_record, payout_props, "notes", f"ダミー稼働者の支払明細テスト用（{args.via}）")

    payout_id = add_record(base, headers, APP_PAYOUTS, payout_record)

    print("✅ ダミー稼働者と支払明細テストデータを作成しました")
    print(f"worker_record_id={worker_id}")
    print(f"dummy_worker_id={candidate_worker_id}")
    print(f"actual_record_id={actual_id}")
    print(f"payout_record_id={payout_id}")
    print(f"period_key={period_key}")
    print(f"via_destination={args.via}")


if __name__ == "__main__":
    main()
