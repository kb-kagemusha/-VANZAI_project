"""
App312（稼働者データ Googleフォーム連携）へ CSV を全件移行する。

- 既存App312レコードを削除して再投入
- 複数行混在値は単一行へ正規化（改行 -> ' / '）

使い方:
  C:/VANZAI_project/.venv/Scripts/python.exe scripts/migrate_app312_from_csv.py
"""

from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
import urllib.parse
import urllib.request
import urllib.error

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
TOKEN_CSV_PATH = BASE_DIR / "kintone_app" / "アプリTOKEN一覧 (VANZAI).csv"
CSV_PATH = BASE_DIR / "kintone_app" / "sample" / "VANZAI：稼働者データ（Googleフォーム連携）.csv"


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def parse_tokens(path: Path) -> dict[int, str]:
    token_by_app: dict[int, str] = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 7:
                continue
            app_id_raw = (row[3] or "").strip()
            token_raw = (row[6] or "").strip()
            if not app_id_raw or not token_raw:
                continue
            if not re.fullmatch(r"\d+", app_id_raw):
                continue
            token_by_app[int(app_id_raw)] = token_raw
    return token_by_app


def normalize_text(value: str) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n+", " / ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_header(value: str) -> str:
    text = str(value or "")
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("･", "・")
    text = re.sub(r"\s+", "", text)
    return text


def kintone_request(
    method: str,
    base_url: str,
    token: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = base_url + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)

    headers = {"X-Cybozu-API-Token": token}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body}") from e


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    for enc in ("utf-8-sig", "cp932", "shift_jis"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                return [dict(row) for row in reader]
        except UnicodeDecodeError:
            continue
    raise RuntimeError("CSV decode failed")


def parse_form_timestamp(value: str) -> datetime:
    text = normalize_text(value)
    if not text:
        return datetime.min
    for fmt in ("%Y/%m/%d %H:%M", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.min


def consolidate_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        worker_id = normalize_text(row.get("稼働者ID", ""))
        if not worker_id:
            continue
        grouped.setdefault(worker_id, []).append(row)

    merged_rows: list[dict[str, str]] = []
    for _, worker_rows in grouped.items():
        worker_rows.sort(
            key=lambda r: parse_form_timestamp(r.get("タイムスタンプ", "")),
            reverse=True,
        )

        merged: dict[str, str] = {}
        for row in worker_rows:
            for key, value in row.items():
                if key not in merged or not normalize_text(merged.get(key, "")):
                    merged[key] = value

        merged_rows.append(merged)

    return merged_rows


def iter_record_ids(base_url: str, token: str, app_id: int) -> list[str]:
    ids: list[str] = []
    offset = 0
    while True:
        resp = kintone_request(
            "GET",
            base_url,
            token,
            "/records.json",
            params={
                "app": app_id,
                "query": f"order by $id asc limit 500 offset {offset}",
                "fields[0]": "$id",
            },
        )
        records = resp.get("records", [])
        if not records:
            break
        for record in records:
            rid = record.get("$id", {}).get("value")
            if rid:
                ids.append(str(rid))
        offset += 500
    return ids


def delete_all_records(base_url: str, token: str, app_id: int) -> int:
    ids = iter_record_ids(base_url, token, app_id)
    if not ids:
        return 0
    deleted = 0
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        kintone_request(
            "DELETE",
            base_url,
            token,
            "/records.json",
            payload={"app": app_id, "ids": chunk},
        )
        deleted += len(chunk)
    return deleted


def get_app_fields(base_url: str, token: str, app_id: int) -> dict[str, dict[str, Any]]:
    resp = kintone_request(
        "GET",
        base_url,
        token,
        "/app/form/fields.json",
        params={"app": app_id},
    )
    return resp.get("properties", {})


def normalize_option_value(value: str) -> str:
    text = normalize_text(value)
    text = text.replace("#", "")
    if " / " in text:
        text = text.split(" / ")[0].strip()
    return text


def coerce_dropdown(value: str, options: list[str]) -> str:
    normalized = normalize_option_value(value)
    if not normalized:
        return ""
    if normalized in options:
        return normalized
    for option in options:
        if option and (option in normalized or normalized in option):
            return option
    return ""


def build_records(rows: list[dict[str, str]], app_fields: dict[str, dict[str, Any]]) -> list[dict[str, dict[str, str]]]:
    header_to_code = {
        "有効・無効": "is_active",
        "稼働者ID": "worker_id",
        "氏名(姓)": "last_name",
        "氏名(名)": "first_name",
        "姓(フリガナ)": "lastname_furigana",
        "名(フリガナ)": "firstname_furigana",
        "個人事業主屋号": "bussiness_name",
        "性別": "sex",
        "経由先": "group",
        "紹介者/下請け": "introducer_supplier",
        "メールアドレス": "email",
        "郵便番号": "zipcode",
        "都道府県": "pref",
        "市区町村以下": "city_etc",
        "建物名・部屋番号": "name_of_building",
        "建物名･部屋番号": "name_of_building",
        "携帯電話番号": "phone",
        "緊急連絡先氏名(カナ)": "emergency_contact_name",
        "緊急連絡先": "emergency_contact_phone",
        "振込口座(銀行名)": "bank_name",
        "振込口座(支店名)": "bank_branch",
        "振込口座(支店番号)": "bank_branch_number",
        "振込口座(口座種別)": "bank_account_type",
        "振込口座(口座番号7桁)": "bank_account_number",
        "振込口座(名義)": "bank_account_holder",
        "備考": "memos",
        "身分証提出": "id_document",
        "適格請求書発行事業者の登録番号_取得有無": "invoice_registration_status",
        "適格請求書発行事業者の登録番号 （T+13桁の番号を記入してください）": "invoice_registration_number",
        "適格請求書発行事業者の登録番号（T+13桁の番号を記入してください）": "invoice_registration_number",
        "適格請求書発行事業者の登録番号（T+13桁の番号）": "invoice_registration_number",
        "住所 (郵便番号・建物名・部屋番号を除く)": "address_line1",
        "住所 (郵便番号･建物名･部屋番号を除く)": "address_line1",
        "住所(建物名・部屋番号のみ)": "address_line2",
        "住所(建物名･部屋番号のみ)": "address_line2",
    }

    normalized_map = {normalize_header(k): v for k, v in header_to_code.items()}

    app_field_codes = set(app_fields.keys())
    result: list[dict[str, dict[str, str]]] = []
    for row in rows:
        record: dict[str, dict[str, str]] = {}
        for raw_key, raw_val in row.items():
            code = normalized_map.get(normalize_header(raw_key))
            if not code or code not in app_field_codes:
                continue
            value = normalize_text(raw_val)
            if not value:
                continue

            if code == "submitted_at":
                continue

            field_type = app_fields[code].get("type", "")
            if field_type in {"DROP_DOWN", "RADIO_BUTTON"}:
                options_raw = app_fields[code].get("options", {})
                options = [str(k) for k in options_raw.keys()]
                value = coerce_dropdown(value, options)
                if not value:
                    continue

            record[code] = {"value": value}

        if "is_active" in app_field_codes and "is_active" not in record:
            record["is_active"] = {"value": "無効"}

        if "last_name" in record and "first_name" in record and "worker_id" in record:
            result.append(record)

    return result


def add_records(base_url: str, token: str, app_id: int, records: list[dict[str, Any]]) -> int:
    added = 0
    for i in range(0, len(records), 100):
        chunk = records[i:i + 100]
        kintone_request(
            "POST",
            base_url,
            token,
            "/records.json",
            payload={"app": app_id, "records": chunk},
        )
        added += len(chunk)
    return added


def main() -> None:
    env = load_env(ENV_PATH)
    token_by_app = parse_tokens(TOKEN_CSV_PATH)

    subdomain = env.get("KINTONE_SUBDOMAIN")
    guest_space_id = env.get("KINTONE_GUEST_SPACE_ID")
    if not subdomain or not guest_space_id:
        raise RuntimeError("KINTONE_SUBDOMAIN / KINTONE_GUEST_SPACE_ID are required")

    app312_token = token_by_app.get(312)
    if not app312_token:
        raise RuntimeError("App312 token not found in token CSV")

    base_url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1"
    app_id = 312

    raw_rows = read_csv_rows(CSV_PATH)
    rows = consolidate_rows(raw_rows)
    app_fields = get_app_fields(base_url, app312_token, app_id)
    records = build_records(rows, app_fields)

    deleted = delete_all_records(base_url, app312_token, app_id)
    added = add_records(base_url, app312_token, app_id, records)

    print(f"Deleted: {deleted}")
    print(f"CSV rows: {len(raw_rows)}")
    print(f"Merged rows by worker_id: {len(rows)}")
    print(f"Prepared: {len(records)}")
    print(f"Imported: {added}")


if __name__ == "__main__":
    main()
