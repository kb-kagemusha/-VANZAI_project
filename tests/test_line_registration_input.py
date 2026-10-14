"""LINE登録の入力組。"""
from datetime import date

import pytest

from src.domain.line_registration_input import LineRegistrationInputError, normalize_line_registration

UNLINKED = {
    "last_name",
    "first_name",
    "last_name_furigana",
    "first_name_furigana",
    "phone",
    "birth_date",
    "postal_code",
    "prefecture",
    "address1",
}


def _body(**overrides):
    body = {
        "last_name": "山田",
        "first_name": "太郎",
        "last_name_furigana": "やまだ",
        "first_name_furigana": "たろう",
        "phone": "09000001111",
        "email": "",
        "birth_date": "1990-01-02",
        "postal_code": "1000001",
        "prefecture": "東京都",
        "address1": "千代田区1-1",
        "address2": "",
    }
    body.update(overrides)
    return body


def test_unlinked_requires_core_fields():
    sent = set(UNLINKED)
    normalized = normalize_line_registration(_body(), sent=sent, linked=False)
    assert normalized.last_name == "山田"
    assert normalized.address2 == ""
    assert normalized.birth_date == date(1990, 1, 2)
    with pytest.raises(LineRegistrationInputError):
        normalize_line_registration(_body(last_name=""), sent=sent, linked=False)


def test_address_and_name_groups_reject_partial_replace():
    with pytest.raises(LineRegistrationInputError):
        normalize_line_registration(
            {"postal_code": "1000001"},
            sent={"postal_code"},
            linked=True,
        )
    with pytest.raises(LineRegistrationInputError):
        normalize_line_registration(
            {"last_name": "山田", "first_name": ""},
            sent={"last_name", "first_name"},
            linked=True,
        )
    with pytest.raises(LineRegistrationInputError):
        normalize_line_registration({"postal_code": "100-0001"}, sent={"postal_code", "prefecture", "address1"}, linked=True)


def test_blank_contact_does_not_clear_and_future_birth_is_rejected():
    kept = normalize_line_registration({"phone": "  ", "last_name": "山田", "first_name": "太郎"}, sent={"phone", "last_name", "first_name"}, linked=True)
    assert kept.phone is None
    assert kept.last_name == "山田"
    tomorrow = "2999-01-01"
    with pytest.raises(LineRegistrationInputError):
        normalize_line_registration({"birth_date": tomorrow}, sent={"birth_date"}, linked=True)
    with pytest.raises(LineRegistrationInputError):
        normalize_line_registration({}, sent=set(), linked=True)
