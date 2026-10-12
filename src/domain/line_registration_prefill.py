"""本人の稼働者情報を入力項目へ投影する。区切りのない氏名は推測しない。"""
import re
from src.domain.worker_edit_guard import guarded_values

PREFECTURE = re.compile(r"^(北海道|東京都|大阪府|京都府|.{2,3}県)")

def split_name(value):
    parts = re.split(r"[\s　]+", str(value or "").strip(), maxsplit=1)
    return (parts[0], parts[1] if len(parts) > 1 else "")

def split_address(value):
    lines = str(value or "").strip().split("\n", 1)
    first = lines[0]
    match = PREFECTURE.match(first)
    prefecture = match.group(1) if match else ""
    return prefecture, first[len(prefecture):], lines[1] if len(lines) > 1 else ""

def worker_form_values(worker):
    values = guarded_values(worker)
    last, first = split_name(values["name"])
    last_kana, first_kana = split_name(values["furigana"])
    prefecture, address1, address2 = split_address(values["address"])
    return {
        "last_name": last, "first_name": first,
        "last_name_furigana": last_kana, "first_name_furigana": first_kana,
        "phone": values["phone"], "email": values["email"], "birth_date": values["birth_date"],
        "postal_code": values["postal_code"], "prefecture": prefecture,
        "address1": address1, "address2": address2,
        "nearest_station": values["nearest_station"], "station_walk_minutes": values["station_walk_minutes"],
        "emergency_contact_phone": values["emergency_contact_phone"],
        "emergency_contact_name": values["emergency_contact_name"],
        "emergency_contact_relationship": values["emergency_contact_relationship"],
    }
