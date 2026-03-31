"""
App311 / App312 のフィールドコードを業務名に合わせて更新する。

- 入力: kintone_app/アプリTOKEN一覧 (VANZAI).csv のAPIトークン
- 実行: preview 更新 -> deploy

使い方:
  C:/VANZAI_project/.venv/Scripts/python.exe scripts/update_app311_312_field_codes.py
"""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any
import urllib.parse
import urllib.request

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
TOKEN_CSV_PATH = BASE_DIR / "kintone_app" / "アプリTOKEN一覧 (VANZAI).csv"

SYSTEM_TYPES = {
    "CREATOR",
    "CREATED_TIME",
    "MODIFIER",
    "UPDATED_TIME",
    "RECORD_NUMBER",
    "REVISION",
    "__REVISION__",
    "__ID__",
}

PROCESS_TYPES = {"CATEGORY", "STATUS", "STATUS_ASSIGNEE"}


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
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


def normalize_label(value: str) -> str:
    text = str(value or "")
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("　", " ")
    text = re.sub(r"[\s\n\r\t]+", "", text)
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

    data = None
    headers = {"X-Cybozu-API-Token": token}
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}


def get_form_fields(base_url: str, token: str, app_id: int) -> dict[str, Any]:
    resp = kintone_request(
        "GET",
        base_url,
        token,
        "/app/form/fields.json",
        params={"app": app_id},
    )
    return resp.get("properties", {})


def deploy_app(base_url: str, token: str, app_id: int) -> None:
    kintone_request(
        "POST",
        base_url,
        token,
        "/preview/app/deploy.json",
        payload={"apps": [{"app": app_id}]},
    )


def update_field_codes(
    *,
    base_url: str,
    token: str,
    app_id: int,
    label_to_code: dict[str, str],
) -> int:
    properties = get_form_fields(base_url, token, app_id)

    normalized_mapping = {normalize_label(k): v for k, v in label_to_code.items()}

    update_properties: dict[str, Any] = {}
    used_codes = set(properties.keys())

    for old_code, props in properties.items():
        field_type = props.get("type", "")
        label = props.get("label", "")
        if field_type in SYSTEM_TYPES or field_type in PROCESS_TYPES:
            continue
        if not label:
            continue

        mapped_code = normalized_mapping.get(normalize_label(label))
        if not mapped_code:
            continue
        if mapped_code == old_code:
            continue

        if mapped_code in used_codes and mapped_code != old_code:
            continue

        update_properties[old_code] = {
            "type": field_type,
            "code": mapped_code,
            "label": label,
        }
        used_codes.add(mapped_code)

    if not update_properties:
        return 0

    kintone_request(
        "PUT",
        base_url,
        token,
        "/preview/app/form/fields.json",
        payload={"app": app_id, "properties": update_properties},
    )
    deploy_app(base_url, token, app_id)
    return len(update_properties)


def main() -> None:
    env = load_env(ENV_PATH)
    token_by_app = parse_tokens(TOKEN_CSV_PATH)

    subdomain = env.get("KINTONE_SUBDOMAIN")
    guest_space_id = env.get("KINTONE_GUEST_SPACE_ID")
    if not subdomain or not guest_space_id:
        raise RuntimeError("KINTONE_SUBDOMAIN / KINTONE_GUEST_SPACE_ID are required")

    base_url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1"

    app311_map = {
        "有効・無効": "is_active",
        "メールアドレス": "email",
        "代表者名（フルネーム漢字）": "representative_name",
        "代表者名（フリガナ）": "representative_name_furigana",
        "会社名": "company_name",
        "会社名（フリガナ）": "company_name_furigana",
        "郵便番号": "zipcode",
        "都道府県": "pref",
        "市区町村以下": "city_etc",
        "建物名・部屋番号": "name_of_building",
        "建物名･部屋番号": "name_of_building",
        "電話番号": "phone",
        "振込口座(銀行名)": "bank_name",
        "振込口座(支店名)": "bank_branch",
        "振込口座(支店番号)": "bank_branch_number",
        "振込口座(口座種別)": "bank_account_type",
        "振込口座(口座番号7桁)": "bank_account_number",
        "振込口座(カタカナ)": "bank_account_holder_kana",
        "適格請求書発行事業者の登録番号_取得有無": "invoice_registration_status",
        "適格請求書発行事業者の登録番号（T+13桁の番号を記入してください）": "invoice_registration_number",
        "適格請求書発行事業者の登録番号（T+13桁の番号を記入してください": "invoice_registration_number",
        "住所(郵便番号・建物名・部屋番号を除く)": "address_line1",
        "住所(郵便番号･建物名･部屋番号を除く)": "address_line1",
        "住所(建物名・部屋番号のみ)": "address_line2",
        "住所(建物名･部屋番号のみ)": "address_line2",
        "稼働者法人ID": "corporate_worker_id",
        "備考": "memos",
        "タイムスタンプ": "submitted_at",
    }

    app312_map = {
        "有効・無効": "is_active",
        "経由先": "group",
        "適格請求書発行事業者の登録番号_取得有無": "invoice_registration_status",
        "性別": "sex",
        "稼働者ID": "worker_id",
        "氏名(姓)": "last_name",
        "氏名(名)": "first_name",
        "姓(フリガナ)": "lastname_furigana",
        "名(フリガナ)": "firstname_furigana",
        "個人事業主屋号": "bussiness_name",
        "紹介者/下請け": "introducer_supplier",
        "メールアドレス": "email",
        "携帯電話番号": "phone",
        "緊急連絡先氏名(カナ)": "emergency_contact_name",
        "緊急連絡先": "emergency_contact_phone",
        "郵便番号": "zipcode",
        "都道府県": "pref",
        "市区町村以下": "city_etc",
        "建物名・部屋番号": "name_of_building",
        "建物名･部屋番号": "name_of_building",
        "振込口座(銀行名)": "bank_name",
        "振込口座(支店名)": "bank_branch",
        "振込口座(支店番号)": "bank_branch_number",
        "振込口座(口座種別)": "bank_account_type",
        "振込口座(口座番号7桁)": "bank_account_number",
        "振込口座(名義)": "bank_account_holder",
        "備考": "memos",
        "身分証提出": "id_document",
        "適格請求書発行事業者の登録番号（T+13桁の番号）": "invoice_registration_number",
        "住所(郵便番号・建物名・部屋番号を除く)": "address_line1",
        "住所(郵便番号･建物名･部屋番号を除く)": "address_line1",
        "住所(建物名・部屋番号のみ)": "address_line2",
        "住所(建物名･部屋番号のみ)": "address_line2",
        "住所(都道府県~市町村以下)": "address_pref_city",
        "住所(都道府県～市町村以下)": "address_pref_city",
        "支店名": "bank_branch_legacy",
        "支店番号": "bank_branch_number_legacy",
        "住所:郵便番号": "zipcode_legacy",
        "住所：郵便番号": "zipcode_legacy",
        "タイムスタンプ": "submitted_at",
    }

    app311_token = token_by_app.get(311)
    app312_token = token_by_app.get(312)
    if not app311_token or not app312_token:
        raise RuntimeError("App311 / App312 token not found in token CSV")

    changed311 = update_field_codes(
        base_url=base_url,
        token=app311_token,
        app_id=311,
        label_to_code=app311_map,
    )
    changed312 = update_field_codes(
        base_url=base_url,
        token=app312_token,
        app_id=312,
        label_to_code=app312_map,
    )

    print(f"App311 changed fields: {changed311}")
    print(f"App312 changed fields: {changed312}")


if __name__ == "__main__":
    main()
