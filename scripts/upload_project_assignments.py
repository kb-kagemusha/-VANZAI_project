import csv
import re
from pathlib import Path
from typing import Dict, List

import requests

BASE_URL = "https://xtf5wpxp3gk2.cybozu.com"
GUEST_SPACE_ID = "3"
TOKEN_LIST_PATH = Path(r"c:\VANZAI_project\kintone_app\アプリTOKEN一覧 (VANZAI).csv")
DATA_PATH = Path(r"c:\VANZAI_project\kintone_app\project_assignments_data.csv")
APP_NAME = "project_assignments_フィールド定義"

NUMERIC_FIELDS = {"working_hours", "billing_rate_monthly", "billing_rate_daily"}

LABEL_MAP = {
    "assignment_id": "ID",
    "client_name": "会社名",
    "client_manager": "責任者",
    "main_staff": "メイン担当者",
    "category_major": "大カテゴリ",
    "category_middle": "中カテゴリ",
    "category_minor": "小カテゴリ",
    "start_date": "開始期間",
    "end_date": "終了期間",
    "address": "住所",
    "gathering_time": "集合時間",
    "start_time": "開始時間",
    "end_time": "終了時間",
    "dismissal_time": "解散時間",
    "working_hours": "1日稼働時間(h)",
    "detail_url": "詳細リンク",
    "sales_rule": "販売ルール",
    "billing_rate_monthly": "請求単価/月ベース報酬(税抜)",
    "billing_rate_daily": "請求単価/1日1人工/ベース報酬(税抜)",
    "billing_rate_incentive": "請求単価/1日1人工/インセン報酬",
    "notes": "備考",
}


def load_token_info() -> Dict[str, str]:
    if not TOKEN_LIST_PATH.exists():
        raise FileNotFoundError(f"Token list not found: {TOKEN_LIST_PATH}")

    with TOKEN_LIST_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("アプリ名") == APP_NAME:
                app_id = (row.get("アプリID") or "").strip()
                token = (row.get("APIトークン") or "").strip()
                if not app_id or not token:
                    raise ValueError("App ID or API token is missing for project_assignments.")
                return {"app_id": app_id, "token": token}

    raise ValueError(f"App name not found in token list: {APP_NAME}")


def normalize_number(value: str) -> str:
    cleaned = re.sub(r"[^0-9.\-]", "", value)
    return cleaned if cleaned and cleaned != "." else ""


def normalize_label(value: str) -> str:
    return "".join((value or "").split())


def fetch_form_fields(app_id: str, token: str) -> Dict[str, dict]:
    response = requests.get(
        f"{BASE_URL}/k/guest/{GUEST_SPACE_ID}/v1/app/form/fields.json",
        headers={"X-Cybozu-API-Token": token},
        params={"app": app_id},
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("properties", {})


def build_field_code_map(app_id: str, token: str) -> Dict[str, str]:
    properties = fetch_form_fields(app_id, token)
    label_to_code = {
        normalize_label(prop.get("label")): code for code, prop in properties.items()
    }
    field_code_map = {}
    missing = []
    for csv_key, label in LABEL_MAP.items():
        code = label_to_code.get(normalize_label(label))
        if code:
            field_code_map[csv_key] = code
        else:
            missing.append(label)

    if missing:
        print("⚠️ フォームに存在しないフィールドラベル:")
        for label in missing:
            print(f"  - {label}")

    return field_code_map


def load_records(field_code_map: Dict[str, str]) -> List[Dict[str, Dict[str, str]]]:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Data CSV not found: {DATA_PATH}")

    records = []
    with DATA_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            assignment_id = (row.get("assignment_id") or "").strip()
            if not assignment_id:
                continue
            record = {}
            for key, raw_value in row.items():
                field_code = field_code_map.get(key)
                if not field_code:
                    continue
                value = (raw_value or "").strip()
                if key in NUMERIC_FIELDS:
                    value = normalize_number(value)
                record[field_code] = {"value": value}
            records.append(record)
    return records


def fetch_existing_ids(app_id: str, token: str, assignment_code: str) -> set:
    existing_ids = set()
    offset = 0
    while True:
        params = {
            "app": app_id,
            "fields": [assignment_code],
            "query": f"order by レコード番号 asc limit 500 offset {offset}",
        }
        response = requests.get(
            f"{BASE_URL}/k/guest/{GUEST_SPACE_ID}/v1/records.json",
            headers={"X-Cybozu-API-Token": token},
            params=params,
            timeout=30,
        )
        if response.status_code != 200:
            print(f"既存レコード取得に失敗: {response.status_code} {response.text}")
            break
        data = response.json().get("records", [])
        if not data:
            break
        for record in data:
            value = record.get(assignment_code, {}).get("value")
            if value:
                existing_ids.add(value)
        offset += len(data)
    return existing_ids


def create_records(app_id: str, token: str, records: List[Dict[str, Dict[str, str]]]):
    headers = {
        "X-Cybozu-API-Token": token,
        "Content-Type": "application/json",
    }
    url = f"{BASE_URL}/k/guest/{GUEST_SPACE_ID}/v1/records.json"
    batch_size = 100
    created = 0

    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        response = requests.post(
            url,
            headers=headers,
            json={"app": app_id, "records": batch},
            timeout=30,
        )
        response.raise_for_status()
        created += len(batch)
        print(f"  登録完了: {created}/{len(records)}件")

    return created


def main():
    token_info = load_token_info()
    app_id = token_info["app_id"]
    token = token_info["token"]

    field_code_map = build_field_code_map(app_id, token)
    assignment_code = field_code_map.get("assignment_id")
    if not assignment_code:
        raise ValueError("assignment_id のフィールドコードが解決できませんでした。")

    records = load_records(field_code_map)
    print("==== 案件カテゴリ分けレコード登録 ====")
    print(f"アプリID: {app_id}")
    print(f"読み込み件数: {len(records)}")

    existing_ids = fetch_existing_ids(app_id, token, assignment_code)
    if existing_ids:
        before_count = len(records)
        records = [
            record
            for record in records
            if record.get("assignment_id", {}).get("value") not in existing_ids
        ]
        print(f"既存レコードを除外: {before_count - len(records)}件")

    if not records:
        print("追加対象なし（全件登録済み）")
        return

    created = create_records(app_id, token, records)
    print("==== 登録完了 ====")
    print(f"追加件数: {created}")


if __name__ == "__main__":
    main()
