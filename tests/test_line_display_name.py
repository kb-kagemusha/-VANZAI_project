import io
import json
from datetime import datetime, timezone

import pytest
from src.api.jwt_auth import create_user_with_hashed_password

from src.models.base import generate_ulid
from src.models.line_order import LineWorkerLink
from src.models.transaction import AuditLog
from src.services.line_messaging import LineMessagingClient, LineSettings
from tests.test_api_line_order_requests import _auth, _worker, fake_line, ops_user
from tests.test_line_registration_review import _enable, _admin, _submit, _full_body, _choose_new


def _link(db_session, worker, display_name=None):
    link = LineWorkerLink(id=generate_ulid(), worker_id=worker.id, line_user_id="U-trusted-profile",
                          line_display_name=display_name, status="active", linked_at=datetime.now(timezone.utc))
    db_session.add(link)
    db_session.commit()
    return link


def test_refresh_fills_missing_profile_name_using_saved_line_identity(api_client, db_session, ops_user, fake_line, monkeypatch):
    worker = _worker(db_session, "登録の氏名")
    link = _link(db_session, worker)
    seen = []
    def profile(subject):
        seen.append(subject)
        return "LINE上の表示名"
    monkeypatch.setattr(fake_line, "profile_name", profile)
    response = api_client.post(f"/api/order-requests/line-links/{worker.id}/refresh-profile", headers=_auth(ops_user.username))
    assert response.status_code == 200, response.text
    assert response.json()["line_display_name"] == "LINE上の表示名"
    assert seen == ["U-trusted-profile"]
    db_session.expire_all()
    assert db_session.get(LineWorkerLink, link.id).line_display_name == "LINE上の表示名"
    assert worker.name == "登録の氏名"
    assert db_session.query(LineWorkerLink).count() == 1
    listed = api_client.get("/api/order-requests/line-links", headers=_auth(ops_user.username))
    assert listed.json()["items"][0]["line_display_name"] == "LINE上の表示名"
    audit = db_session.query(AuditLog).filter_by(action="line_profile_refreshed").one()
    assert "U-trusted-profile" not in str(audit.after_value)


def test_refresh_failure_preserves_existing_name_and_binding(api_client, db_session, ops_user, fake_line, monkeypatch):
    worker = _worker(db_session, "登録の氏名")
    link = _link(db_session, worker, "以前に取得した表示名")
    monkeypatch.setattr(fake_line, "profile_name", lambda _: None)
    response = api_client.post(f"/api/order-requests/line-links/{worker.id}/refresh-profile", headers=_auth(ops_user.username))
    assert response.status_code == 502
    db_session.expire_all()
    assert db_session.get(LineWorkerLink, link.id).line_display_name == "以前に取得した表示名"
    assert db_session.get(LineWorkerLink, link.id).status == "active"


def test_refresh_rejects_link_change_during_profile_fetch(api_client, db_session, ops_user, fake_line, monkeypatch):
    worker = _worker(db_session, "登録の氏名")
    link = _link(db_session, worker)
    def changed(_):
        link.status = "revoked"
        db_session.add(LineWorkerLink(id=generate_ulid(), worker_id=worker.id, line_user_id="U-other-person",
                                     line_display_name="別の本人", status="active", linked_at=datetime.now(timezone.utc)))
        db_session.commit()
        return "古い本人の表示名"
    monkeypatch.setattr(fake_line, "profile_name", changed)
    response = api_client.post(f"/api/order-requests/line-links/{worker.id}/refresh-profile", headers=_auth(ops_user.username))
    assert response.status_code == 409
    db_session.expire_all()
    current = db_session.query(LineWorkerLink).filter_by(worker_id=worker.id, status="active").one()
    assert current.line_user_id == "U-other-person" and current.line_display_name == "別の本人"


def test_refresh_does_not_fetch_revoked_or_unauthorized_links(api_client, db_session, ops_user, fake_line, monkeypatch):
    accounting_user = create_user_with_hashed_password(db=db_session, username="profile_accounting",
        email="profile_accounting@example.com", password="test-password", role="accounting")
    db_session.commit()
    worker = _worker(db_session, "登録の氏名")
    link = _link(db_session, worker)
    calls = []
    monkeypatch.setattr(fake_line, "profile_name", lambda subject: calls.append(subject))
    url = f"/api/order-requests/line-links/{worker.id}/refresh-profile"
    assert api_client.post(url).status_code == 401
    assert api_client.post(url, headers=_auth(accounting_user.username)).status_code == 403
    link.status = "revoked"
    db_session.commit()
    assert api_client.post(url, headers=_auth(ops_user.username)).status_code == 404
    assert calls == []


def test_new_registration_approval_keeps_working_if_profile_is_unavailable(api_client, db_session, monkeypatch):
    _enable(monkeypatch)
    admin = _admin(db_session)
    request_id, _ = _submit(api_client, _full_body(), "unavailable-profile")
    headers = _auth(admin.username)
    compared = _choose_new(api_client, request_id, headers)
    class Unavailable:
        def profile_name(self, subject):
            raise TimeoutError()
    monkeypatch.setattr("src.services.line_registration_review.build_line_client", Unavailable)
    approved = api_client.post(f"/api/line/registration/reviews/{request_id}/approve",
                              json={"comparison_ticket": compared["comparison_ticket"]}, headers=headers)
    assert approved.status_code == 200, approved.text
    link = db_session.query(LineWorkerLink).filter_by(worker_id=approved.json()["worker_id"]).one()
    assert link.line_display_name is None and link.status == "active"


@pytest.mark.parametrize("payload, expected", [
    ({"userId": "U-profile", "displayName": "  LINEの名前  "}, "LINEの名前"),
    ({"userId": "U-another", "displayName": "別の本人"}, None),
    ({"displayName": "本人未確認"}, None),
    ({"userId": "U-profile", "displayName": " "}, None),
    ([], None),
])
def test_profile_transport_checks_response_subject(monkeypatch, payload, expected):
    monkeypatch.setattr("src.services.line_messaging.line_settings", lambda: LineSettings("test", "test", "fake-token", "test"))
    monkeypatch.setattr("src.services.line_messaging.urllib.request.urlopen", lambda request, timeout: io.BytesIO(json.dumps(payload).encode()))
    assert LineMessagingClient().profile_name("U-profile") == expected
