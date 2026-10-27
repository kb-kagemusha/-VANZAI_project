import csv
from pathlib import Path
from typing import Dict, List, Tuple

import requests

BASE_URL = "https://xtf5wpxp3gk2.cybozu.com"
GUEST_SPACE_ID = "3"
TOKEN_LIST_PATH = Path(r"c:\VANZAI_project\kintone_app\アプリTOKEN一覧 (VANZAI).csv")
APP_NAME = "project_assignments_フィールド定義"

FIELDS = [
    "$id",
    "assignment_id",
    "category_major",
    "category_middle",
    "category_minor",
]


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


def fetch_records(app_id: str, token: str) -> List[dict]:
    records = []
    offset = 0
    while True:
        params = {
            "app": app_id,
            "fields": FIELDS,
            "query": f"order by レコード番号 asc limit 500 offset {offset}",
        }
        response = requests.get(
            f"{BASE_URL}/k/guest/{GUEST_SPACE_ID}/v1/records.json",
            headers={"X-Cybozu-API-Token": token},
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        batch = response.json().get("records", [])
        if not batch:
            break
        records.extend(batch)
        offset += len(batch)
    return records


def fetch_form_fields(app_id: str, token: str) -> Dict[str, dict]:
    response = requests.get(
        f"{BASE_URL}/k/guest/{GUEST_SPACE_ID}/v1/app/form/fields.json",
        headers={"X-Cybozu-API-Token": token},
        params={"app": app_id},
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("properties", {})


def summarize(records: List[dict]) -> Tuple[int, int, int, List[str]]:
    total = len(records)
    with_assignment = 0
    empty_rows = 0
    empty_ids = []

    for record in records:
        assignment_id = (record.get("assignment_id", {}) or {}).get("value", "")
        category_major = (record.get("category_major", {}) or {}).get("value", "")
        category_middle = (record.get("category_middle", {}) or {}).get("value", "")
        category_minor = (record.get("category_minor", {}) or {}).get("value", "")
        record_id = (record.get("$id", {}) or {}).get("value", "")

        if assignment_id:
            with_assignment += 1
        if not assignment_id and not category_major and not category_middle and not category_minor:
            empty_rows += 1
            if record_id and len(empty_ids) < 10:
                empty_ids.append(record_id)

    return total, with_assignment, empty_rows, empty_ids


def main():
    token_info = load_token_info()
    app_id = token_info["app_id"]
    token = token_info["token"]

    print("==== 案件カテゴリ分けアプリ レコード確認 ====")
    print(f"アプリID: {app_id}")

    records = fetch_records(app_id, token)
    try:
        properties = fetch_form_fields(app_id, token)
        if properties:
            field_codes = sorted(properties.keys())
            print("フォームフィールドコード:", ", ".join(field_codes))
            print("フォームフィールド詳細(先頭20件):")
            for index, (code, prop) in enumerate(sorted(properties.items())):
                if index >= 20:
                    break
                label = prop.get("label", "")
                field_type = prop.get("type", "")
                print(f"  - {label} ({code}) [{field_type}]")
    except requests.HTTPError as exc:
        print(f"フォームフィールド取得エラー: {exc}")
    if records:
        sample_keys = [key for key in records[0].keys() if not key.startswith("$")]
        print("フィールドコード(先頭レコード):", ", ".join(sample_keys))
    total, with_assignment, empty_rows, empty_ids = summarize(records)

    print(f"総レコード数: {total}")
    print(f"assignment_idあり: {with_assignment}")
    print(f"主要カテゴリ全て空: {empty_rows}")
    if empty_ids:
        print("空レコードID(先頭10件):", ", ".join(empty_ids))


if __name__ == "__main__":
    main()
