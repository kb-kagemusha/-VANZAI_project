"""LINE申請を稼働者の9項目へ反映する。空欄は消さない。住所は届いた組で置き換える。"""
from __future__ import annotations

from datetime import date

from src.domain.worker_edit_guard import GUARDED_FIELDS, guarded_values


def empty_worker_values() -> dict[str, str]:
    return {field: "" for field in GUARDED_FIELDS}


def project_worker_values(before: dict[str, str], detail) -> dict[str, str]:
    after = {field: before.get(field, "") for field in GUARDED_FIELDS}
    last_name = _text(detail.last_name)
    first_name = _text(detail.first_name)
    if last_name and first_name:
        after["name"] = f"{last_name} {first_name}"
    last_kana = _text(detail.last_name_furigana)
    first_kana = _text(detail.first_name_furigana)
    if last_kana and first_kana:
        after["furigana"] = f"{last_kana} {first_kana}"
    phone = _text(detail.phone)
    if phone:
        after["phone"] = phone
    email = _text(detail.email)
    if email:
        after["email"] = email
    if detail.birth_date is not None:
        after["birth_date"] = detail.birth_date.isoformat()
    station = _text(detail.nearest_station)
    if station:
        after["nearest_station"] = station
    if detail.station_walk_minutes is not None:
        after["station_walk_minutes"] = str(detail.station_walk_minutes)
    if _address_sent(detail):
        building = _text(detail.building_address)
        address = f"{_text(detail.prefecture)}{_text(detail.city_address)}"
        if building:
            address = f"{address}\n{building}"
        after["postal_code"] = _text(detail.zipcode)
        after["address"] = address
    return after


def values_from_worker(worker) -> dict[str, str]:
    return guarded_values(worker)


def assign_worker_values(worker, values: dict[str, str]) -> None:
    worker.name = values["name"]
    worker.furigana = values["furigana"] or None
    worker.phone = values["phone"] or None
    worker.email = values["email"] or None
    worker.birth_date = date.fromisoformat(values["birth_date"]) if values["birth_date"] else None
    worker.postal_code = values["postal_code"] or None
    worker.address = values["address"] or None
    worker.nearest_station = values["nearest_station"] or None
    worker.station_walk_minutes = int(values["station_walk_minutes"]) if values["station_walk_minutes"] else None


def changed_fields(before: dict[str, str], after: dict[str, str]) -> dict[str, dict[str, str]]:
    return {
        field: {"before": before[field], "after": after[field]}
        for field in GUARDED_FIELDS
        if before.get(field, "") != after.get(field, "")
    }


def submitted_components(detail) -> dict[str, str]:
    birth = detail.birth_date.isoformat() if detail.birth_date else ""
    return {
        "last_name": _text(detail.last_name),
        "first_name": _text(detail.first_name),
        "last_name_furigana": _text(detail.last_name_furigana),
        "first_name_furigana": _text(detail.first_name_furigana),
        "phone": _text(detail.phone),
        "email": _text(detail.email),
        "birth_date": birth,
        "postal_code": _text(detail.zipcode),
        "prefecture": _text(detail.prefecture),
        "address1": _text(detail.city_address),
        "address2": _text(detail.building_address),
        "nearest_station": _text(detail.nearest_station),
        "station_walk_minutes": _text(detail.station_walk_minutes),
    }


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _address_sent(detail) -> bool:
    return any(
        getattr(detail, name) is not None
        for name in ("zipcode", "prefecture", "city_address", "building_address")
    )
