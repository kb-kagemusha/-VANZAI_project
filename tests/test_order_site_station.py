"""会場の最寄り駅と徒歩分（起床の締切の計算に使う。DEC-066）。"""
import json

import pytest

from src.models.enums import Permission
from src.services.auth import ROLE_PERMISSIONS
from src.models.enums import UserRole
from src.services.order_request_format import apply_template_fields, parse_sections
from src.services.order_request_pdf import _headed_fields


def _conditions(**extra):
    return json.dumps({"format": "additional-request-v1", "project_name": "駅前イベント", **extra}, ensure_ascii=False)


def test_station_and_walk_minutes_are_saved_and_shown():
    conditions, body = apply_template_fields(
        _conditions(site_station="新宿駅（南口）", site_station_walk_minutes=5), "", work_date_label="10月25日", site_name="会場A",
    )
    stored = json.loads(conditions)
    assert stored["site_station"] == "新宿駅（南口）" and stored["site_station_walk_minutes"] == 5
    fields = dict(_headed_fields(body))
    assert fields["最寄り駅"] == "新宿駅（南口）（徒歩5分）"
    assert body.index("■稼働場所") < body.index("■最寄り駅")


@pytest.mark.parametrize("minutes", ["", None])
def test_walk_minutes_are_optional(minutes):
    conditions, body = apply_template_fields(
        _conditions(site_station="渋谷駅", site_station_walk_minutes=minutes), "", work_date_label="", site_name="会場",
    )
    assert json.loads(conditions)["site_station_walk_minutes"] is None
    assert dict(_headed_fields(body))["最寄り駅"] == "渋谷駅"


def test_no_station_means_no_heading_and_legacy_data_reads():
    conditions, body = apply_template_fields(_conditions(site_station_walk_minutes=3), "", work_date_label="", site_name="会場")
    assert "■最寄り駅" not in body
    legacy = parse_sections(_conditions())
    assert legacy["site_station"] == "" and "site_station_walk_minutes" not in legacy


@pytest.mark.parametrize("minutes", [-1, 121, "5分", 2.5, True])
def test_invalid_walk_minutes_are_rejected(minutes):
    with pytest.raises(ValueError):
        parse_sections(_conditions(site_station="新宿駅", site_station_walk_minutes=minutes))


def test_station_name_length_is_limited():
    with pytest.raises(ValueError):
        parse_sections(_conditions(site_station="駅" * 101))


def test_wake_alert_permission_is_granted_per_role():
    assert Permission.WAKE_ALERT_RECEIVE in ROLE_PERMISSIONS[UserRole.ADMIN]
    assert Permission.WAKE_ALERT_RECEIVE not in ROLE_PERMISSIONS[UserRole.OPS]
