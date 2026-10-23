"""DEC-075: explicit none/yes, backward-compatible notes, confirm and reuse."""
import json

import pytest
from src.services.order_request_format import parse_sections, canonical_conditions, compose_document, incentive_details
from tests.test_api_order_requests import _auth, _worker, ops_user, pdf_root  # noqa: F401
from tests.test_line_daily import _payload


@pytest.mark.parametrize("note,enabled", [("", False), ("なし", False), ("※インセン無し", False), ("インセンティブなし", False), ("販売1台につき500円", True), ("条件によっては支給なし", True)])
def test_legacy_note_inference_is_conservative(note, enabled):
    assert incentive_details({"incentive": note}) == (enabled, note if enabled else "インセンティブなし")


def test_explicit_none_is_canonical_and_invalid_boolean_is_rejected():
    sections = parse_sections(json.dumps({"format": "additional-request-v1", "incentive_enabled": False, "incentive": "誤った自由文"}))
    assert sections["incentive"] == "インセンティブなし"
    assert json.loads(canonical_conditions(sections))["incentive_enabled"] is False
    assert "■インセンティブ：\nインセンティブなし" in compose_document(sections, work_date_label="日程", site_name="会場")
    with pytest.raises(ValueError):
        parse_sections(json.dumps({"format": "additional-request-v1", "incentive_enabled": "false"}))


def test_incentive_flag_and_note_survive_save_template_and_confirmation(api_client, db_session, ops_user, pdf_root):
    worker = _worker(db_session, "インセンティブ確認用")
    payload = _payload([worker.id])
    conditions = json.loads(payload["request_conditions"])
    conditions.update(incentive_enabled=True, incentive="")
    payload["request_conditions"] = json.dumps(conditions)
    auth = _auth(ops_user.username)
    created = api_client.post("/api/order-requests", headers=auth, json=payload)
    assert created.status_code == 200, created.text
    row = created.json()
    assert json.loads(row["request_conditions"])["incentive_enabled"] is True
    rejected = api_client.post(f"/api/order-requests/versions/{row['id']}/confirm", headers=auth)
    assert rejected.status_code == 400 and "インセンティブの詳細" in rejected.json()["detail"]
    conditions["incentive"] = "販売1台につき500円\n翌月に実績確定"
    updated = api_client.patch(f"/api/order-requests/versions/{row['id']}", headers=auth, json={"request_conditions": json.dumps(conditions)})
    assert updated.status_code == 200, updated.text
    template = api_client.post("/api/order-requests/templates", headers=auth, json={"name": "インセンティブあり", "source_version_id": row["id"]})
    assert template.status_code == 200, template.text
    detail = api_client.get(f"/api/order-requests/templates/{template.json()['id']}", headers=auth).json()
    stored = json.loads(detail["payload"]["request_conditions"])
    assert stored["incentive_enabled"] is True and stored["incentive"] == conditions["incentive"]
    confirmed = api_client.post(f"/api/order-requests/versions/{row['id']}/confirm", headers=auth)
    assert confirmed.status_code == 200, confirmed.text
    assert conditions["incentive"] in confirmed.json()["body"]
