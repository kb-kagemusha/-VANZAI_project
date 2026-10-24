import csv
from pathlib import Path

import requests

BASE_URL = "https://xtf5wpxp3gk2.cybozu.com"
GUEST_SPACE_ID = "3"
TARGET_MIDDLE = "TP開拓"
TOKEN_LIST_PATH = Path(r"c:\VANZAI_project\kintone_app\アプリTOKEN一覧 (VANZAI).csv")


def load_token_info():
    with TOKEN_LIST_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("アプリ名") == "案件種別マスタ (project_types)":
                app_id = (row.get("アプリID") or "").strip()
                token = (row.get("APIトークン") or "").strip()
                if not app_id or not token:
                    raise ValueError("App ID or API token missing for project_types")
                return app_id, token
    raise ValueError("project_types entry not found in token list")


def main():
    app_id, token = load_token_info()
    params = {
        "app": app_id,
        "fields": ["name", "parent_middle"],
        "query": f'category_level = "minor" and parent_middle = "{TARGET_MIDDLE}"'
    }
    response = requests.get(
        f"{BASE_URL}/k/guest/{GUEST_SPACE_ID}/v1/records.json",
        headers={"X-Cybozu-API-Token": token},
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    records = response.json().get("records", [])
    print("==== 小カテゴリ確認 ====")
    print(f"中カテゴリ: {TARGET_MIDDLE}")
    print(f"件数: {len(records)}")
    for record in records:
        print(record.get("name", {}).get("value", ""))


if __name__ == "__main__":
    main()
