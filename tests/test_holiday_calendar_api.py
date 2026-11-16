"""Shared holiday overrides are versioned, audited and reflected in later previews."""
from src.models.transaction import AuditLog
from tests.test_order_billing import admin_user  # noqa: F401
from tests.test_api_order_requests import _auth


def test_shared_calendar_changes_are_audited_and_stale_updates_rejected(api_client, db_session, admin_user):
    headers = _auth(admin_user.username)
    url = "/api/order-requests/holiday-calendar"
    params = {"start": "2027-01-01", "end": "2027-01-15"}
    response = api_client.get(url, params=params, headers=headers)
    assert response.status_code == 200, response.text
    original = next(day for day in response.json() if day["day"] == "2027-01-11")
    assert original["is_holiday"] and original["revision"] == 0
    change = {"day": original["day"], "is_holiday": False, "name": "", "revision": 0}
    response = api_client.put(url, headers=headers, json=change)
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 1
    assert api_client.put(url, headers=headers, json=change).status_code == 409
    day = next(item for item in api_client.get(url, params=params, headers=headers).json() if item["day"] == original["day"])
    assert day["is_holiday"] is False
    assert db_session.query(AuditLog).filter_by(action="holiday_calendar_changed", target_id=original["day"]).count() == 1
    response = api_client.put(url, headers=headers, json={"day": original["day"], "is_holiday": True, "name": "祝日", "revision": 1})
    assert response.status_code == 200, response.text
    assert db_session.query(AuditLog).filter_by(action="holiday_calendar_changed", target_id=original["day"]).count() == 2


def test_confirming_candidates_persists_them_and_rejects_a_stale_review(api_client, db_session, admin_user):
    headers = _auth(admin_user.username)
    url = "/api/order-requests/holiday-calendar"
    params = {"start": "2027-01-01", "end": "2027-01-15"}
    days = [item["day"] for item in api_client.get(url, params=params, headers=headers).json() if item["is_holiday"]]
    response = api_client.post(url + "/confirm", headers=headers, json={**params, "days": days})
    assert response.status_code == 200, response.text
    assert all(item["revision"] == 1 for item in response.json())
    assert db_session.query(AuditLog).filter_by(action="holiday_calendar_initialized").count() == len(days)
    assert api_client.post(url + "/confirm", headers=headers, json={**params, "days": days}).status_code == 200
    change = {"day": "2027-01-11", "is_holiday": False, "name": "", "revision": 1}
    assert api_client.put(url, headers=headers, json=change).status_code == 200
    response = api_client.post(url + "/confirm", headers=headers, json={**params, "days": days})
    assert response.status_code == 409
