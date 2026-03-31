import csv
from pathlib import Path

import requests

BASE_URL = "https://xtf5wpxp3gk2.cybozu.com"
GUEST_SPACE_ID = "3"
TOKEN_LIST_PATH = Path(r"c:\VANZAI_project\kintone_app\アプリTOKEN一覧 (VANZAI).csv")
APP_NAME = "案件種別マスタ (project_types)"


def load_token_info():
    with TOKEN_LIST_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("アプリ名") == APP_NAME:
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
        "fields": ["name", "category_level", "type_id"],
        "query": 'category_level = "major" order by type_id asc'
    }
    response = requests.get(
        f"{BASE_URL}/k/guest/{GUEST_SPACE_ID}/v1/records.json",
        headers={"X-Cybozu-API-Token": token},
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    records = response.json().get("records", [])
    majors = []
    for record in records:
        majors.append(record.get("name", {}).get("value", ""))

    print("==== App164 大カテゴリ一覧 ====")
    print("件数:", len(majors))
    for name in majors:
        print(name)


if __name__ == "__main__":
    main()
