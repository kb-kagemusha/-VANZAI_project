import csv
import json
import os
import re
import sys
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
CSV_PATH = os.path.join(BASE_DIR, "kintone_app", "sample", "スタッフ名簿：VANZAI.csv")


def load_env(path):
    env = {}
    if not os.path.exists(path):
        raise FileNotFoundError(f".env not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def kintone_request(method, base_url, token, path, params=None, payload=None):
    url = base_url + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    data = None
    headers = {"X-Cybozu-API-Token": token}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"HTTP {e.code}: {body}") from e


def get_form_fields(base_url, token, app_id):
    params = {"app": app_id}
    resp = kintone_request("GET", base_url, token, "/app/form/fields.json", params=params)
    properties = resp.get("properties", {})
    fields_by_label = {}
    fields_by_code = {}
    for code, props in properties.items():
        label = props.get("label") or ""
        fields_by_code[normalize_header(code)] = code
        if label:
            fields_by_label[normalize_header(label)] = code
    return fields_by_label, fields_by_code


def iter_record_ids(base_url, token, app_id):
    offset = 0
    while True:
        query = f"order by $id asc limit 500 offset {offset}"
        params = {"app": app_id, "query": query, "fields[0]": "$id"}
        resp = kintone_request("GET", base_url, token, "/records.json", params=params)
        records = resp.get("records", [])
        if not records:
            break
        for record in records:
            rid = record.get("$id", {}).get("value")
            if rid:
                yield rid
        offset += 500


def delete_all_records(base_url, token, app_id):
    ids = list(iter_record_ids(base_url, token, app_id))
    if not ids:
        return 0
    total_deleted = 0
    chunk_size = 100
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i : i + chunk_size]
        payload = {"app": app_id, "ids": chunk}
        kintone_request("DELETE", base_url, token, "/records.json", payload=payload)
        total_deleted += len(chunk)
    return total_deleted


def read_csv_rows(path):
    encodings = ["utf-8-sig", "cp932", "shift_jis"]
    last_error = None
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            return rows
        except UnicodeDecodeError as e:
            last_error = e
    raise last_error


def split_name_and_furigana(raw_name):
    name = raw_name.strip()
    furigana = ""
    match = re.match(r"^(.*?)\s*[（(](.*?)[)）]\s*$", raw_name.strip())
    if match:
        name = match.group(1).strip()
        furigana = match.group(2).strip()
    if " " not in name and "　" not in name and len(name) >= 3:
        name = name[:2] + " " + name[2:]
    return name, furigana


def normalize_header(value):
    if value is None:
        return ""
    text = str(value)
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("･", "・")
    return "".join(ch for ch in text if ch not in " \t\r\n")


def resolve_field_code(fields_by_label, fields_by_code, *candidates):
    for candidate in candidates:
        if not candidate:
            continue
        normalized = normalize_header(candidate)
        if normalized in fields_by_code:
            return fields_by_code[normalized]
        if normalized in fields_by_label:
            return fields_by_label[normalized]
    return ""


def pick_value(row, normalized_row, *keys):
    for key in keys:
        raw = (row.get(key) or "").strip() if key in row else ""
        if raw:
            return raw
        norm_key = normalize_header(key)
        raw = (normalized_row.get(norm_key) or "").strip()
        if raw:
            return raw
    return ""


def build_worker_records(rows, fields_by_label, fields_by_code):
    records = []
    counters = {"VZ": 0, "ST": 0}

    code_worker_id = resolve_field_code(fields_by_label, fields_by_code, "worker_id", "稼働者ID")
    code_name = resolve_field_code(fields_by_label, fields_by_code, "name", "氏名")
    code_last_name = resolve_field_code(fields_by_label, fields_by_code, "last_name", "氏名(姓)")
    code_first_name = resolve_field_code(fields_by_label, fields_by_code, "first_name", "氏名(名)")
    code_furigana = resolve_field_code(fields_by_label, fields_by_code, "furigana", "フリガナ", "ふりがな")
    code_last_name_furigana = resolve_field_code(fields_by_label, fields_by_code, "lastname_furigana", "姓(フリガナ)")
    code_first_name_furigana = resolve_field_code(fields_by_label, fields_by_code, "firstname_furigana", "名(フリガナ)")
    code_email = resolve_field_code(fields_by_label, fields_by_code, "email", "メールアドレス")
    code_phone = resolve_field_code(fields_by_label, fields_by_code, "phone", "携帯電話番号", "電話番号")
    code_full_part = resolve_field_code(fields_by_label, fields_by_code, "full_part", "常勤・スポット", "常勤orスポット")
    code_group = resolve_field_code(fields_by_label, fields_by_code, "group", "所属", "経由先")
    code_introducer = resolve_field_code(fields_by_label, fields_by_code, "introducer_supplier", "introducer_name", "紹介者/下請け", "下請けor紹介者", "紹介者", "下請け")
    code_gender = resolve_field_code(fields_by_label, fields_by_code, "sex", "gender", "性別")
    code_business_name = resolve_field_code(fields_by_label, fields_by_code, "bussiness_name", "business_name", "個人事業主の屋号", "個人事業主屋号", "屋号")
    code_postal = resolve_field_code(fields_by_label, fields_by_code, "zipcode", "postal_code", "郵便番号")
    code_prefecture = resolve_field_code(fields_by_label, fields_by_code, "pref", "prefecture", "都道府県")
    code_city = resolve_field_code(fields_by_label, fields_by_code, "city_etc", "city", "市区町村以下", "市町村以下")
    code_building = resolve_field_code(fields_by_label, fields_by_code, "name_of_building", "building", "建物名･部屋番号", "建物名・部屋番号")
    code_address = resolve_field_code(fields_by_label, fields_by_code, "address", "住所")

    for row in rows:
        normalized_row = {normalize_header(k): (v or "") for k, v in row.items()}
        worker_id = pick_value(row, normalized_row, "稼働者ID", "worker_id")

        last_name = pick_value(row, normalized_row, "氏名(姓)", "姓")
        first_name = pick_value(row, normalized_row, "氏名(名)", "名")
        name_value = " ".join(part for part in [last_name, first_name] if part).strip()

        furigana_last = pick_value(row, normalized_row, "姓(フリガナ)")
        furigana_first = pick_value(row, normalized_row, "名(フリガナ)")
        furigana_value = " ".join(part for part in [furigana_last, furigana_first] if part).strip()

        raw_name = pick_value(row, normalized_row, "氏名（よみがな）", "氏名(よみがな)", "氏名")
        if raw_name and (not name_value or not furigana_value):
            parsed_name, parsed_furigana = split_name_and_furigana(raw_name)
            if not name_value:
                name_value = parsed_name
            if not furigana_value:
                furigana_value = parsed_furigana

        if not worker_id:
            raw_group = pick_value(row, normalized_row, "所属", "経由先")
            affiliation = "VANZAI" if raw_group == "VANZAI" else "現場"
            prefix = "VZ" if affiliation == "VANZAI" else "ST"
            counters[prefix] += 1
            worker_id = f"{prefix}{str(counters[prefix]).zfill(3)}"

        if not name_value:
            continue

        group_value = pick_value(row, normalized_row, "所属", "経由先")
        full_part_value = pick_value(row, normalized_row, "常勤・スポット", "常勤orスポット")
        email_value = pick_value(row, normalized_row, "メールアドレス", "email")
        phone_value = pick_value(row, normalized_row, "携帯電話番号", "phone")
        introducer_value = pick_value(row, normalized_row, "下請けor紹介者")
        gender_value = pick_value(row, normalized_row, "性別")
        business_name_value = pick_value(row, normalized_row, "個人事業主屋号")
        postal_value = pick_value(row, normalized_row, "郵便番号")
        prefecture_value = pick_value(row, normalized_row, "都道府県")
        city_value = pick_value(row, normalized_row, "市区町村以下")
        building_value = pick_value(row, normalized_row, "建物名･部屋番号", "建物名・部屋番号")

        record = {"is_active": {"value": "有効"}}
        if code_worker_id:
            record[code_worker_id] = {"value": worker_id}
        if code_last_name and last_name:
            record[code_last_name] = {"value": last_name}
        if code_first_name and first_name:
            record[code_first_name] = {"value": first_name}
        if code_name and name_value:
            record[code_name] = {"value": name_value}
        if code_group and group_value:
            record[code_group] = {"value": group_value}
        if code_last_name_furigana and furigana_last:
            record[code_last_name_furigana] = {"value": furigana_last}
        if code_first_name_furigana and furigana_first:
            record[code_first_name_furigana] = {"value": furigana_first}
        if code_furigana and furigana_value:
            record[code_furigana] = {"value": furigana_value}
        if code_full_part and full_part_value:
            record[code_full_part] = {"value": full_part_value}
        if code_email and email_value:
            record[code_email] = {"value": email_value}
        if code_phone and phone_value:
            record[code_phone] = {"value": phone_value}
        if code_introducer and introducer_value:
            record[code_introducer] = {"value": introducer_value}
        if code_gender and gender_value:
            record[code_gender] = {"value": gender_value}
        if code_business_name and business_name_value:
            record[code_business_name] = {"value": business_name_value}
        if code_postal and postal_value:
            record[code_postal] = {"value": postal_value}
        if code_prefecture and prefecture_value:
            record[code_prefecture] = {"value": prefecture_value}
        if code_city and city_value:
            record[code_city] = {"value": city_value}
        if code_building and building_value:
            record[code_building] = {"value": building_value}
        if code_address:
            address_lines = []
            if postal_value:
                address_lines.append(f"〒{postal_value}")
            address_body = "".join(part for part in [prefecture_value, city_value] if part)
            if address_body:
                address_lines.append(address_body)
            if building_value:
                address_lines.append(building_value)
            if address_lines:
                record[code_address] = {"value": "\n".join(address_lines)}
        records.append(record)

    return records


def add_records(base_url, token, app_id, records):
    total = 0
    chunk_size = 100
    for i in range(0, len(records), chunk_size):
        chunk = records[i : i + chunk_size]
        payload = {"app": app_id, "records": chunk}
        kintone_request("POST", base_url, token, "/records.json", payload=payload)
        total += len(chunk)
    return total


def iter_records(base_url, token, app_id, fields):
    offset = 0
    while True:
        params = {
            "app": app_id,
            "query": f"order by $id asc limit 500 offset {offset}",
        }
        for idx, field_code in enumerate(fields):
            params[f"fields[{idx}]"] = field_code
        resp = kintone_request("GET", base_url, token, "/records.json", params=params)
        records = resp.get("records", [])
        if not records:
            break
        for record in records:
            yield record
        offset += 500


def summarize_field_coverage(base_url, token, app_id, field_codes):
    if not field_codes:
        return
    counts = {code: 0 for code in field_codes}
    total = 0
    for record in iter_records(base_url, token, app_id, field_codes):
        total += 1
        for code in field_codes:
            value = record.get(code, {}).get("value")
            if value not in (None, ""):
                counts[code] += 1
    print("Field coverage:")
    print(f"  total_records: {total}")
    for code in field_codes:
        print(f"  {code}: {counts[code]}")


def main():
    env = load_env(ENV_PATH)
    subdomain = env.get("KINTONE_SUBDOMAIN")
    guest_space_id = env.get("KINTONE_GUEST_SPACE_ID")
    token = env.get("KINTONE_TOKEN_WORKERS")

    if not subdomain or not guest_space_id or not token:
        raise RuntimeError("KINTONE_SUBDOMAIN / KINTONE_GUEST_SPACE_ID / KINTONE_TOKEN_WORKERS are required.")

    base_url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1"
    app_id = 165

    fields_by_label, fields_by_code = get_form_fields(base_url, token, app_id)

    print("Deleting all records from App165...")
    deleted = delete_all_records(base_url, token, app_id)
    print(f"Deleted: {deleted}")

    print("Loading CSV...")
    rows = read_csv_rows(CSV_PATH)
    records = build_worker_records(rows, fields_by_label, fields_by_code)
    print(f"Prepared records: {len(records)}")

    if not records:
        print("No records to import. Exiting.")
        return

    print("Importing records...")
    added = add_records(base_url, token, app_id, records)
    print(f"Imported: {added}")

    coverage_fields = [
        resolve_field_code(fields_by_label, fields_by_code, "worker_id", "稼働者ID"),
        resolve_field_code(fields_by_label, fields_by_code, "last_name", "氏名(姓)"),
        resolve_field_code(fields_by_label, fields_by_code, "first_name", "氏名(名)"),
        resolve_field_code(fields_by_label, fields_by_code, "lastname_furigana", "姓(フリガナ)"),
        resolve_field_code(fields_by_label, fields_by_code, "firstname_furigana", "名(フリガナ)"),
        resolve_field_code(fields_by_label, fields_by_code, "introducer_supplier", "紹介者/下請け"),
        resolve_field_code(fields_by_label, fields_by_code, "zipcode", "郵便番号"),
        resolve_field_code(fields_by_label, fields_by_code, "pref", "都道府県"),
        resolve_field_code(fields_by_label, fields_by_code, "city_etc", "市区町村以下"),
        resolve_field_code(fields_by_label, fields_by_code, "name_of_building", "建物名･部屋番号"),
    ]
    coverage_fields = [code for code in coverage_fields if code]
    summarize_field_coverage(base_url, token, app_id, coverage_fields)


if __name__ == "__main__":
    main()
