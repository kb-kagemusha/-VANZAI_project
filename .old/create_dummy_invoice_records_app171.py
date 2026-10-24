"""App171（請求書）に見積確認用ダミーレコードを投入するスクリプト。

用途:
- front_dashboard.js の「見積書・請求書の発行」導線で画面確認するための最低限データを作る

実行例:
  C:/VANZAI_project/.venv/Scripts/python.exe scripts/create_dummy_invoice_records_app171.py --year 2026 --month 2 --count 3
"""

from __future__ import annotations

import argparse
import base64
import os
from datetime import datetime

import requests
from dotenv import load_dotenv


def build_base_url(subdomain: str, guest_space_id: str | None) -> str:
    if guest_space_id:
        return f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1"
    return f"https://{subdomain}.cybozu.com/k/v1"


def admin_headers(user: str, password: str, include_content_type: bool = True) -> dict[str, str]:
    auth = base64.b64encode(f"{user}:{password}".encode()).decode()
    headers = {"X-Cybozu-Authorization": auth}
    if include_content_type:
        headers["Content-Type"] = "application/json"
    return headers


def get_fields(base_url: str, headers: dict[str, str], app_id: int) -> dict:
    resp = requests.get(
        f"{base_url}/app/form/fields.json",
        headers=headers,
        params={"app": app_id},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("properties", {})


def get_records(base_url: str, headers: dict[str, str], app_id: int, query: str, fields: list[str] | None = None) -> list[dict]:
    params: dict[str, object] = {"app": app_id, "query": query}
    if fields:
        params["fields"] = fields
    resp = requests.get(
        f"{base_url}/records.json",
        headers=headers,
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("records", [])


def add_records(base_url: str, headers: dict[str, str], app_id: int, records: list[dict]) -> dict:
    payload = {"app": app_id, "records": records}
    resp = requests.post(
        f"{base_url}/records.json",
        headers=headers,
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def find_field_code(properties: dict, code_candidates: list[str], label_keywords: list[str]) -> str:
    for code in code_candidates:
        if code in properties:
            return code

    lower_keywords = [k.lower() for k in label_keywords]
    for code, prop in properties.items():
        label = str(prop.get("label", "")).lower()
        if any(k in label for k in lower_keywords):
            return code
    return ""


def pick_option_value(prop: dict, prefer_keywords: list[str] | None = None) -> str:
    options = prop.get("options", {}) or {}
    option_keys = list(options.keys())
    if not option_keys:
        return ""

    if prefer_keywords:
        for key in option_keys:
            text = str(key)
            if any(keyword in text for keyword in prefer_keywords):
                return key
            label = str(options.get(key, {}).get("label", ""))
            if any(keyword in label for keyword in prefer_keywords):
                return key

    return option_keys[0]


def default_value_for_required(prop: dict, idx: int, year: int, month: int) -> object:
    ftype = prop.get("type", "")
    if ftype in ("SINGLE_LINE_TEXT", "RICH_TEXT", "LINK"):
        return f"DUMMY_{year}{month:02d}_{idx}"
    if ftype == "MULTI_LINE_TEXT":
        return f"ダミー入力 {year}-{month:02d} #{idx}"
    if ftype == "NUMBER":
        return str(10000 + idx)
    if ftype == "DATE":
        return f"{year}-{month:02d}-01"
    if ftype == "TIME":
        return "09:00"
    if ftype == "DATETIME":
        return f"{year}-{month:02d}-01T09:00:00+09:00"
    if ftype in ("DROP_DOWN", "RADIO_BUTTON"):
        return pick_option_value(prop)
    if ftype in ("CHECK_BOX", "MULTI_SELECT"):
        picked = pick_option_value(prop)
        return [picked] if picked else []
    return ""


def resolve_responsible_name(base_url: str, headers: dict[str, str]) -> str:
    # App307 (project_assignments) の owner_name を優先
    try:
        records = get_records(
            base_url,
            headers,
            307,
            "order by $id desc limit 50",
            ["owner_name"],
        )
        for record in records:
            val = str(record.get("owner_name", {}).get("value", "")).strip()
            if val:
                return val
    except Exception:
        pass

    # App309 (staff_managers) の name を次点で使用
    try:
        records = get_records(
            base_url,
            headers,
            309,
            "order by $id desc limit 50",
            ["name"],
        )
        for record in records:
            val = str(record.get("name", {}).get("value", "")).strip()
            if val:
                return val
    except Exception:
        pass

    return "ダミー責任者"


def build_dummy_record(
    properties: dict,
    period_code: str,
    type_code: str,
    owner_code: str,
    subject_code: str,
    amount_code: str,
    estimate_value: str,
    responsible: str,
    year: int,
    month: int,
    idx: int,
) -> dict:
    period_key = f"{year}{month:02d}"
    record: dict[str, dict] = {}

    if period_code:
        record[period_code] = {"value": period_key}
    if type_code:
        prop = properties.get(type_code, {})
        if prop.get("type") in ("CHECK_BOX", "MULTI_SELECT"):
            record[type_code] = {"value": [estimate_value]}
        else:
            record[type_code] = {"value": estimate_value}
    if owner_code:
        record[owner_code] = {"value": responsible}
    if subject_code:
        record[subject_code] = {"value": f"{year}年{month}月分_ダミー見積_{idx}"}
    if amount_code:
        record[amount_code] = {"value": str(120000 + (idx * 10000))}

    # 必須未充足を埋める
    skip_types = {
        "RECORD_NUMBER",
        "CREATOR",
        "CREATED_TIME",
        "MODIFIER",
        "UPDATED_TIME",
        "STATUS",
        "STATUS_ASSIGNEE",
        "REFERENCE_TABLE",
        "SUBTABLE",
        "CALC",
        "LABEL",
        "SPACER",
        "HR",
    }

    for code, prop in properties.items():
        if code in record:
            continue
        if not prop.get("required", False):
            continue
        if prop.get("type") in skip_types:
            continue
        default_value = default_value_for_required(prop, idx, year, month)
        if default_value == "":
            continue
        record[code] = {"value": default_value}

    return record


def main() -> None:
    parser = argparse.ArgumentParser(description="App171に見積確認用ダミーデータを作成")
    parser.add_argument("--year", type=int, default=datetime.now().year)
    parser.add_argument("--month", type=int, default=datetime.now().month)
    parser.add_argument("--count", type=int, default=3)
    args = parser.parse_args()

    if args.year < 2000 or args.year > 2100:
        raise ValueError("yearは2000〜2100で指定してください")
    if args.month < 1 or args.month > 12:
        raise ValueError("monthは1〜12で指定してください")
    if args.count < 1 or args.count > 20:
        raise ValueError("countは1〜20で指定してください")

    load_dotenv(override=True)

    subdomain = os.getenv("KINTONE_SUBDOMAIN", "").strip()
    guest_space_id = os.getenv("KINTONE_GUEST_SPACE_ID", "").strip() or None
    admin_user = os.getenv("KINTONE_ADMIN_USER", "").strip()
    admin_password = os.getenv("KINTONE_ADMIN_PASSWORD", "").strip()
    app_id = int(os.getenv("KINTONE_APP_INVOICES", "171"))

    if not subdomain or not admin_user or not admin_password:
        raise RuntimeError("KINTONE_SUBDOMAIN / KINTONE_ADMIN_USER / KINTONE_ADMIN_PASSWORD が必要です")

    base_url = build_base_url(subdomain, guest_space_id)
    headers = admin_headers(admin_user, admin_password)
    headers_no_ct = admin_headers(admin_user, admin_password, include_content_type=False)

    properties = get_fields(base_url, headers_no_ct, app_id)
    period_code = find_field_code(properties, ["period_key"], ["期間", "対象月", "年月"])
    type_code = find_field_code(properties, ["document_type", "invoice_type", "doc_type"], ["見積", "請求", "帳票種別"])
    owner_code = find_field_code(properties, ["owner_name", "responsible_name", "client_manager"], ["責任者", "担当者"])
    subject_code = find_field_code(properties, ["subject", "subject_manual", "title"], ["件名", "タイトル"])
    amount_code = find_field_code(properties, ["total_amount", "amount", "billing_amount", "grand_total"], ["合計", "金額", "請求額"])

    if not period_code:
        raise RuntimeError("App171に期間フィールド（period_key相当）が見つかりません")
    if not type_code:
        raise RuntimeError("App171に帳票種別フィールド（document_type相当）が見つかりません")

    type_prop = properties.get(type_code, {})
    estimate_value = pick_option_value(type_prop, prefer_keywords=["見積", "estimate"]) or "見積書"
    responsible = resolve_responsible_name(base_url, headers_no_ct)

    records: list[dict] = []
    for i in range(1, args.count + 1):
        records.append(
            build_dummy_record(
                properties=properties,
                period_code=period_code,
                type_code=type_code,
                owner_code=owner_code,
                subject_code=subject_code,
                amount_code=amount_code,
                estimate_value=estimate_value,
                responsible=responsible,
                year=args.year,
                month=args.month,
                idx=i,
            )
        )

    result = add_records(base_url, headers, app_id, records)

    print("=" * 60)
    print(f"✅ App{app_id} にダミー見積データを投入しました")
    print(f"  period_key: {args.year}{args.month:02d}")
    print(f"  document_type: {estimate_value}")
    print(f"  responsible: {responsible}")
    print(f"  追加件数: {len(result.get('ids', []))}")
    print(f"  record_ids: {result.get('ids', [])}")
    print("=" * 60)


if __name__ == "__main__":
    main()
