"""期間の休業日と、送付先ごとの個人不参加日（DEC-065、A0）。"""
import copy
import json

import pytest

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.domain.order_schedule import expand_work_days, normalize_schedule, schedule_text, work_dates
from src.models.base import generate_ulid
from src.models.enums import UserRole
from src.models.master import Worker
from src.models.order_request import OrderRequestVersion
from tests.test_order_schedule import schedule


def _with_holidays(*days):
    value = schedule()
    value["work_groups"][1]["excluded_dates"] = list(days)
    return value


# ---- 日程の検証と展開 -------------------------------------------------------

def test_excluded_dates_are_sorted_and_removed_from_work_days():
    value = normalize_schedule(_with_holidays("2027-03-05", "2027-03-03"))
    assert value["work_groups"][1]["excluded_dates"] == ["2027-03-03", "2027-03-05"]
    days = work_dates(value)
    assert "2027-03-03" not in days and "2027-03-05" not in days
    assert days[0] == "2027-03-01" and days[-1] == "2027-03-10"
    assert len(days) == 1 + 9 - 2
    expanded = expand_work_days(value)
    assert {d["work_group_id"] for d in expanded} == {"day1", "rest"}
    assert all(d["start_time"] for d in expanded)


def test_legacy_schedule_without_excluded_dates_reads_as_empty():
    value = schedule()
    assert "excluded_dates" not in value["work_groups"][1]
    normalized = normalize_schedule(value)
    assert normalized["work_groups"][1]["excluded_dates"] == []
    assert len(work_dates(normalized)) == 10


@pytest.mark.parametrize("days", [["2027-03-11"], ["2027-02-28"], ["2027-03-04", "2027-03-04"], ["2027-3-04"]])
def test_out_of_range_duplicate_or_malformed_holidays_are_rejected(days):
    with pytest.raises(ValueError):
        normalize_schedule(_with_holidays(*days))


def test_single_day_cannot_have_holidays():
    value = schedule()
    value["work_groups"][0]["excluded_dates"] = ["2027-03-01"]
    with pytest.raises(ValueError):
        normalize_schedule(value)


def test_period_with_all_days_excluded_cannot_be_confirmed():
    all_days = [f"2027-03-{d:02d}" for d in range(2, 11)]
    draft = normalize_schedule(_with_holidays(*all_days))
    assert draft["work_groups"][1]["excluded_dates"] == all_days
    with pytest.raises(ValueError):
        normalize_schedule(_with_holidays(*all_days), complete=True)


def test_shrinking_period_does_not_silently_drop_holidays():
    value = _with_holidays("2027-03-09")
    value["work_groups"][1]["to"] = "2027-03-08"
    value["rate_groups"][1]["to"] = "2027-03-08"
    with pytest.raises(ValueError):
        normalize_schedule(value)


def test_holiday_label_is_shown_in_document_text():
    label, hours, _fee = schedule_text(normalize_schedule(_with_holidays("2027-03-03")))
    assert "2027年3月2日～2027年3月10日（休業日：3月3日）" in label
    assert "（休業日：3月3日）" in hours


def test_rate_coverage_checks_only_actual_work_days():
    value = _with_holidays("2027-03-10")
    value["rates_follow_work"] = False
    for rate in value["rate_groups"]:
        rate["work_group_id"] = None
    value["rate_groups"][1]["to"] = "2027-03-09"
    normalize_schedule(value, complete=True)  # 休業日の3/10に単価は不要
    value["work_groups"][1]["excluded_dates"] = []
    with pytest.raises(ValueError):
        normalize_schedule(value, complete=True)


# ---- 個人の不参加日（API） ----------------------------------------------------

def _auth(username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': username})}"}


@pytest.fixture
def ops(db_session):
    user = create_user_with_hashed_password(
        db=db_session, username="absence_ops", email="absence_ops@example.com",
        password="pass123", role=UserRole.OPS.value,
    )
    db_session.commit()
    return user


@pytest.fixture
def pdf_root(tmp_path, monkeypatch):
    monkeypatch.setenv("PDF_STORAGE_ROOT", str(tmp_path))
    return tmp_path


def _worker(db_session, name):
    worker = Worker(id=generate_ulid(), name=name, is_active=True)
    db_session.add(worker)
    db_session.commit()
    return worker


def _payload(worker_ids, value=None, **extra):
    conditions = json.dumps({"format": "additional-request-v1", "project_name": "期間イベント", "schedule": value or _with_holidays("2027-03-03")})
    body = {
        "kind": "formal", "work_date_label": "", "site_name": "会場", "request_conditions": conditions,
        "body": "", "contact_name": "依頼担当", "contact_desk": "", "worker_ids": worker_ids,
        "phone_first": False, "follow_up_due_on": "2027-02-20", "follow_up_due_time": "21:00",
    }
    body.update(extra)
    return body


def test_absences_are_saved_per_recipient_and_dropped_for_removed_recipients(api_client, db_session, ops):
    a, b = _worker(db_session, "Aさん"), _worker(db_session, "Bさん")
    created = api_client.post(
        "/api/order-requests",
        json=_payload([a.id, b.id], recipient_absences={a.id: ["2027-03-04", "2027-03-02", "2027-03-04"], "not-a-recipient": ["2027-03-05"]}),
        headers=_auth(ops.username),
    )
    assert created.status_code == 200, created.text
    data = created.json()
    assert data["draft_recipient_absences"] == {a.id: ["2027-03-02", "2027-03-04"]}
    # 共通本文・PDFの元データに個人の日付が入らない
    assert "2027-03-04" not in data["request_conditions"] and "3月4日" not in data["body"]

    updated = api_client.patch(
        f"/api/order-requests/versions/{data['id']}", json={"worker_ids": [b.id]}, headers=_auth(ops.username),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["draft_recipient_absences"] == {}


@pytest.mark.parametrize("day", ["2027-03-03", "2027-03-11", "2027/03/04"])
def test_absence_must_be_an_actual_work_day(api_client, db_session, ops, day):
    a = _worker(db_session, "Aさん")
    response = api_client.post(
        "/api/order-requests", json=_payload([a.id], recipient_absences={a.id: [day]}), headers=_auth(ops.username),
    )
    assert response.status_code == 400, response.text


def test_absences_require_a_structured_schedule(api_client, db_session, ops):
    a = _worker(db_session, "Aさん")
    response = api_client.post(
        "/api/order-requests",
        json=_payload([a.id], request_conditions="自由文の条件", recipient_absences={a.id: ["2027-03-02"]}),
        headers=_auth(ops.username),
    )
    assert response.status_code == 400, response.text


def test_confirm_rejects_a_recipient_with_zero_offered_days(api_client, db_session, ops, pdf_root):
    a, b = _worker(db_session, "Aさん"), _worker(db_session, "Bさん")
    value = schedule()
    value["work_groups"] = value["work_groups"][:1]
    value["rate_groups"] = value["rate_groups"][:1]
    created = api_client.post(
        "/api/order-requests", json=_payload([a.id, b.id], value=value, recipient_absences={a.id: ["2027-03-01"]}),
        headers=_auth(ops.username),
    )
    assert created.status_code == 200, created.text
    confirmed = api_client.post(f"/api/order-requests/versions/{created.json()['id']}/confirm", headers=_auth(ops.username))
    assert confirmed.status_code == 400
    assert "Aさん" in confirmed.json()["detail"]


def test_other_recipients_are_not_affected_and_revision_copies_absences(api_client, db_session, ops, pdf_root):
    a, b = _worker(db_session, "Aさん"), _worker(db_session, "Bさん")
    created = api_client.post(
        "/api/order-requests", json=_payload([a.id, b.id], recipient_absences={a.id: ["2027-03-02"]}),
        headers=_auth(ops.username),
    )
    version_id = created.json()["id"]
    confirmed = api_client.post(f"/api/order-requests/versions/{version_id}/confirm", headers=_auth(ops.username))
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["draft_recipient_absences"] == {a.id: ["2027-03-02"]}
    # 確定後は変更できない
    blocked = api_client.patch(
        f"/api/order-requests/versions/{version_id}", json={"recipient_absences": {}}, headers=_auth(ops.username),
    )
    assert blocked.status_code == 409
    revised = api_client.post(f"/api/order-requests/versions/{version_id}/revise", json={"reason": "日程の確認"}, headers=_auth(ops.username))
    assert revised.status_code == 200, revised.text
    assert revised.json()["draft_recipient_absences"] == {a.id: ["2027-03-02"]}
    version = db_session.get(OrderRequestVersion, version_id)
    assert b.id not in (version.draft_recipient_absences or {})


def test_revoke_view_endpoint_is_removed(api_client, db_session, ops, pdf_root):
    a = _worker(db_session, "Aさん")
    created = api_client.post("/api/order-requests", json=_payload([a.id]), headers=_auth(ops.username))
    confirmed = api_client.post(f"/api/order-requests/versions/{created.json()['id']}/confirm", headers=_auth(ops.username))
    delivery_id = confirmed.json()["deliveries"][0]["id"]
    response = api_client.post(f"/api/order-requests/deliveries/{delivery_id}/revoke-view", headers=_auth(ops.username))
    assert response.status_code in (404, 405)


def test_document_copy_is_independent_of_input():
    value = _with_holidays("2027-03-03")
    before = copy.deepcopy(value)
    normalize_schedule(value)
    assert value == before
