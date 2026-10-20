import csv
from pathlib import Path
from typing import Dict, List, Set, Tuple

import requests

BASE_URL = "https://xtf5wpxp3gk2.cybozu.com"
GUEST_SPACE_ID = "3"
TOKEN_LIST_PATH = Path(r"c:\VANZAI_project\kintone_app\アプリTOKEN一覧 (VANZAI).csv")
ASSIGNMENTS_PATH = Path(r"c:\VANZAI_project\kintone_app\project_assignments_data.csv")
PROJECT_TYPES_PATH = Path(r"c:\VANZAI_project\kintone_app\project_types_sjis.csv")
APP_NAME = "案件種別マスタ (project_types)"


def load_token_info() -> Tuple[str, str]:
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


def load_assignment_minors() -> Set[Tuple[str, str, str]]:
    if not ASSIGNMENTS_PATH.exists():
        raise FileNotFoundError(f"Assignments CSV not found: {ASSIGNMENTS_PATH}")
    minors = set()
    with ASSIGNMENTS_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            major = (row.get("category_major") or "").strip()
            middle = (row.get("category_middle") or "").strip()
            minor = (row.get("category_minor") or "").strip()
            if not major or not middle or not minor:
                continue
            minors.add((major, middle, minor))
    return minors


def fetch_existing_records(app_id: str, token: str) -> List[dict]:
    records = []
    offset = 0
    while True:
        params = {
            "app": app_id,
            "fields": ["type_id", "name", "category_level", "parent_major", "parent_middle"],
            "query": f"order by type_id asc limit 500 offset {offset}",
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


def parse_type_id(value: str) -> int:
    if not value or not value.startswith("PT"):
        return 0
    try:
        return int(value[2:])
    except ValueError:
        return 0


def build_existing_minor_set(records: List[dict]) -> Set[Tuple[str, str]]:
    existing = set()
    for record in records:
        level = record.get("category_level", {}).get("value", "")
        if level != "minor":
            continue
        minor = record.get("name", {}).get("value", "")
        parent_middle = record.get("parent_middle", {}).get("value", "")
        if minor and parent_middle:
            existing.add((parent_middle, minor))
    return existing


def build_next_type_ids(records: List[dict], count: int) -> List[str]:
    max_id = 0
    for record in records:
        max_id = max(max_id, parse_type_id(record.get("type_id", {}).get("value", "")))
    return [f"PT{str(max_id + i).zfill(3)}" for i in range(1, count + 1)]


def add_records(app_id: str, token: str, records: List[dict]) -> None:
    if not records:
        return
    url = f"{BASE_URL}/k/guest/{GUEST_SPACE_ID}/v1/records.json"
    headers = {"X-Cybozu-API-Token": token, "Content-Type": "application/json"}
    batch_size = 100
    created = 0
    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        response = requests.post(url, headers=headers, json={"app": app_id, "records": batch}, timeout=30)
        response.raise_for_status()
        created += len(batch)
        print(f"  追加完了: {created}/{len(records)}件")


def append_to_master_csv(new_rows: List[Tuple[str, str, str, str, str]]) -> int:
    if not PROJECT_TYPES_PATH.exists():
        raise FileNotFoundError(f"Project types CSV not found: {PROJECT_TYPES_PATH}")

    existing_keys = set()
    with PROJECT_TYPES_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            key = (row.get("category_level"), row.get("name"), row.get("parent_middle"))
            existing_keys.add(key)

    appended = 0
    with PROJECT_TYPES_PATH.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        for row in new_rows:
            key = (row[2], row[1], row[4])
            if key in existing_keys:
                continue
            writer.writerow(row)
            appended += 1
    return appended


def main():
    app_id, token = load_token_info()
    assignment_minors = load_assignment_minors()
    records = fetch_existing_records(app_id, token)
    existing_minor_set = build_existing_minor_set(records)

    missing = []
    for major, middle, minor in sorted(assignment_minors):
        if (middle, minor) not in existing_minor_set:
            missing.append((major, middle, minor))

    print("==== 不足小カテゴリ確認 ====")
    print(f"対象: {len(assignment_minors)}件")
    print(f"不足: {len(missing)}件")

    if not missing:
        return

    type_ids = build_next_type_ids(records, len(missing))
    new_records = []
    csv_rows = []
    for index, (major, middle, minor) in enumerate(missing):
        type_id = type_ids[index]
        new_records.append(
            {
                "type_id": {"value": type_id},
                "name": {"value": minor},
                "category_level": {"value": "minor"},
                "parent_major": {"value": major},
                "parent_middle": {"value": middle},
            }
        )
        csv_rows.append([type_id, minor, "minor", major, middle])

    print("==== App164 追加 ====")
    add_records(app_id, token, new_records)

    appended = append_to_master_csv(csv_rows)
    print("==== CSV更新 ====")
    print(f"project_types_sjis.csv 追加: {appended}件")


if __name__ == "__main__":
    main()
