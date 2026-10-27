"""LINE登録の入力を組ごとに検証する。マスタへの反映は承認時に限る。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

_POSTAL = re.compile(r"^[0-9]{7}$")
_PHONE = re.compile(r"^[0-9+\-]{1,20}$")
_TOKYO = ZoneInfo("Asia/Tokyo")


class LineRegistrationInputError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class NormalizedRegistration:
    last_name: str | None
    first_name: str | None
    last_name_furigana: str | None
    first_name_furigana: str | None
    phone: str | None
    email: str | None
    birth_date: date | None
    postal_code: str | None
    prefecture: str | None
    address1: str | None
    address2: str | None
    address_sent: bool
    additional_stations: list[dict] | None = None
    nearest_station: str | None = None
    station_walk_minutes: int | None = None
    emergency_contact_phone: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_relationship: str | None = None

    def has_change(self) -> bool:
        return any(
            (
                self.last_name,
                self.last_name_furigana,
                self.phone,
                self.email,
                self.birth_date,
                self.address_sent,
                self.additional_stations is not None,
                self.nearest_station,
                self.station_walk_minutes is not None,
                self.emergency_contact_phone,
            )
        )

    def canonical(self) -> dict[str, object]:
        values: dict[str, object] = {
            "last_name": self.last_name,
            "first_name": self.first_name,
            "last_name_furigana": self.last_name_furigana,
            "first_name_furigana": self.first_name_furigana,
            "phone": self.phone,
            "email": self.email,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "postal_code": self.postal_code,
            "prefecture": self.prefecture,
            "address1": self.address1,
            "address2": self.address2 if self.address_sent else None,
        }
        if self.additional_stations is not None:
            values["additional_stations"] = self.additional_stations
        # Keep hashes of existing requests stable when the new fields are blank.
        if self.nearest_station is not None:
            values["nearest_station"] = self.nearest_station
        if self.station_walk_minutes is not None:
            values["station_walk_minutes"] = self.station_walk_minutes
        for field in ("emergency_contact_phone", "emergency_contact_name", "emergency_contact_relationship"):
            if getattr(self, field) is not None:
                values[field] = getattr(self, field)
        return values


def canonicalize_line_registration(payload: dict, *, sent: set[str]) -> NormalizedRegistration:
    """組の形式だけを確認する。紐付けの有無による必須判定はしない。"""
    last_name, first_name = _pair(payload, sent, "last_name", "first_name", "氏名", 100, 100)
    last_kana, first_kana = _pair(
        payload, sent, "last_name_furigana", "first_name_furigana", "ふりがな", 200, 100
    )
    phone = _optional_text(payload, sent, "phone")
    if phone is not None and not _PHONE.fullmatch(phone):
        raise LineRegistrationInputError("電話番号は20文字以内の数字、ハイフン、+で入力してください。")
    email = _optional_text(payload, sent, "email")
    if email is not None and ("@" not in email or len(email) > 255):
        raise LineRegistrationInputError("メールアドレスの形式を確認してください。")
    birth = _birth_date(payload, sent)
    address = _address(payload, sent)
    extra_stations = None
    if "additional_stations" in sent and payload.get("additional_stations") not in (None, ""):
        from src.domain.worker_stations import parse_additional_stations
        try:
            extra_stations = parse_additional_stations(payload["additional_stations"])
        except (ValueError, TypeError) as exc:
            raise LineRegistrationInputError("追加の最寄り駅は駅名（100文字以内）と徒歩時間（0〜300分の整数・任意）で入力してください。") from exc
    station = _optional_text(payload, sent, "nearest_station")
    if station is not None and len(station) > 100:
        raise LineRegistrationInputError("最寄り駅は100文字以内で入力してください。")
    walk = _optional_text(payload, sent, "station_walk_minutes")
    if walk is not None and (not re.fullmatch(r"[0-9]{1,3}", walk) or not 0 <= int(walk) <= 300):
        raise LineRegistrationInputError("最寄り駅までの徒歩時間は0〜300分の整数で入力してください。")
    contact_phone = _optional_text(payload, sent, "emergency_contact_phone")
    contact_name = _optional_text(payload, sent, "emergency_contact_name")
    relation = _optional_text(payload, sent, "emergency_contact_relationship")
    if any((contact_phone, contact_name, relation)):
        if not all((contact_phone, contact_name, relation)):
            raise LineRegistrationInputError("緊急連絡先を変えるときは、電話番号・お名前・関係をすべて入力してください。")
        if not _PHONE.fullmatch(contact_phone):
            raise LineRegistrationInputError("緊急連絡先の電話番号は20文字以内の数字、ハイフン、+で入力してください。")
        if len(contact_name) > 200 or len(relation) > 50:
            raise LineRegistrationInputError("緊急連絡先のお名前は200文字以内、関係は50文字以内で入力してください。")
    normalized = NormalizedRegistration(
        last_name=last_name,
        first_name=first_name,
        last_name_furigana=last_kana,
        first_name_furigana=first_kana,
        phone=phone,
        email=email,
        birth_date=birth,
        postal_code=address[0],
        prefecture=address[1],
        address1=address[2],
        address2=address[3],
        address_sent=address[4],
        additional_stations=extra_stations,
        nearest_station=station,
        station_walk_minutes=int(walk) if walk is not None else None,
        emergency_contact_phone=contact_phone,
        emergency_contact_name=contact_name,
        emergency_contact_relationship=relation,
    )
    return normalized


def normalize_line_registration(payload: dict, *, sent: set[str], linked: bool, full_required: bool = False) -> NormalizedRegistration:
    normalized = canonicalize_line_registration(payload, sent=sent)
    last_name = normalized.last_name
    first_name = normalized.first_name
    last_kana = normalized.last_name_furigana
    first_kana = normalized.first_name_furigana
    phone = normalized.phone
    birth = normalized.birth_date
    if linked:
        if not normalized.has_change():
            raise LineRegistrationInputError("変更する項目を1つ以上入力してください。")
        return normalized
    missing = []
    if not last_name or not first_name:
        missing.append("氏名")
    if not last_kana or not first_kana:
        missing.append("ふりがな")
    if not phone:
        missing.append("電話")
    if birth is None:
        missing.append("生年月日")
    if not normalized.address_sent or not normalized.postal_code or not normalized.prefecture or not normalized.address1:
        missing.append("住所")
    if full_required:
        if not normalized.email:
            missing.append("メール")
        if not normalized.nearest_station:
            missing.append("最寄り駅")
        if normalized.station_walk_minutes is None:
            missing.append("最寄り駅までの徒歩時間")
        if not all((normalized.emergency_contact_phone, normalized.emergency_contact_name, normalized.emergency_contact_relationship)):
            missing.append("緊急連絡先の電話番号・お名前・関係")
    if missing:
        raise LineRegistrationInputError("未紐付けの登録には、" + "、".join(missing) + "が必要です。")
    return normalized


def _pair(
    payload: dict,
    sent: set[str],
    left_key: str,
    right_key: str,
    label: str,
    limit: int,
    part_limit: int,
) -> tuple[str | None, str | None]:
    left_sent = left_key in sent
    right_sent = right_key in sent
    left = _trimmed(payload.get(left_key)) if left_sent else ""
    right = _trimmed(payload.get(right_key)) if right_sent else ""
    if not left and not right:
        return None, None
    if not left or not right:
        raise LineRegistrationInputError(f"{label}は姓と名の両方を入力してください。")
    if len(left) > part_limit or len(right) > part_limit:
        raise LineRegistrationInputError(f"{label}の姓と名はそれぞれ{part_limit}文字以内にしてください。")
    combined = f"{left} {right}"
    if len(combined) > limit:
        raise LineRegistrationInputError(f"{label}は{limit}文字以内にしてください。")
    return left, right


def _optional_text(payload: dict, sent: set[str], key: str) -> str | None:
    if key not in sent:
        return None
    value = _trimmed(payload.get(key))
    return value or None


def _birth_date(payload: dict, sent: set[str]) -> date | None:
    if "birth_date" not in sent:
        return None
    raw = _trimmed(payload.get("birth_date"))
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as exc:
        raise LineRegistrationInputError("生年月日は実在する日付を入力してください。") from exc
    if parsed > datetime.now(_TOKYO).date():
        raise LineRegistrationInputError("生年月日は今日以前の日付を入力してください。")
    return parsed


def _address(payload: dict, sent: set[str]) -> tuple[str | None, str | None, str | None, str | None, bool]:
    keys = ("postal_code", "prefecture", "address1", "address2")
    if not any(key in sent for key in keys):
        return None, None, None, None, False
    postal = _trimmed(payload.get("postal_code")) if "postal_code" in sent else ""
    prefecture = _trimmed(payload.get("prefecture")) if "prefecture" in sent else ""
    address1 = _trimmed(payload.get("address1")) if "address1" in sent else ""
    address2 = _trimmed(payload.get("address2")) if "address2" in sent else ""
    if not postal or not prefecture or not address1:
        raise LineRegistrationInputError("住所を変えるときは、郵便番号、都道府県、市区町村・番地を入力してください。")
    if not _POSTAL.fullmatch(postal):
        raise LineRegistrationInputError("郵便番号は7桁の数字で入力してください。")
    if len(prefecture) > 50:
        raise LineRegistrationInputError("都道府県は50文字以内にしてください。")
    return postal, prefecture, address1, address2, True


def _trimmed(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()
