"""Operator invite/approval boundaries without real LINE traffic."""
from datetime import timedelta
import json
import pytest
from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.master import RegistrationRequest, VanzaiStaff, User, Worker
from src.models.operator_registration import OperatorRegistrationDetail
from src.models.operator_staff import LineStaffLink
from src.models.transaction import AuditLog
from src.services.operator_registration import digest, now
from src.services.line_id_token import LineIdTokenError


@pytest.fixture
def operator_setup(db_session, monkeypatch):
    monkeypatch.setenv("LINE_OPERATOR_REGISTRATION_ENABLED", "true")
    monkeypatch.setenv("LINE_OPERATOR_LIFF_ID", "1234567890-Operator")
    monkeypatch.setenv("LINE_LOGIN_CHANNEL_ID", "1234567890")
    monkeypatch.setattr("src.api.operator_registration_routes.verify_id_token", lambda token, channel: "U-" + token)
    class Fake:
        def profile_name(self, subject): return "検証LINE名"
    fake = Fake()
    monkeypatch.setattr("src.api.operator_registration_routes.build_line_client", lambda: fake)
    monkeypatch.setattr("src.services.operator_registration.build_line_client", lambda: fake)
    user = create_user_with_hashed_password(db=db_session, username="invite-admin", email="invite-admin@example.test", password="test-only-password", role="admin")
    db_session.commit()
    return {"Authorization": "Bearer " + create_access_token({"sub": user.username})}, fake


def invite(api_client, operator_setup):
    response = api_client.post("/api/operator-registration/invitations", headers=operator_setup[0])
    assert response.status_code == 201, response.text
    row = response.json()
    row["token"] = row["url"].split("invite=")[1]
    return row


def submit(api_client, invitation, **changes):
    return api_client.post("/api/line/operator-registration/submissions", json={"invite": invitation["token"], "id_token": "verified-person", "name": "運営 試験", "phone": "０９０－１２３４－５６７８", **changes})


def test_submit_then_admin_approve_creates_only_operator_and_link(api_client, db_session, operator_setup):
    invitation = invite(api_client, operator_setup)
    stored = db_session.get(RegistrationRequest, invitation["request_id"])
    assert stored.public_token_hash == digest(invitation["token"])
    assert invitation["token"] not in json.dumps(api_client.get("/api/operator-registration/invitations", headers=operator_setup[0]).json())
    response = submit(api_client, invitation)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "pending"
    assert db_session.query(VanzaiStaff).count() == db_session.query(LineStaffLink).count() == db_session.query(Worker).count() == 0
    assert db_session.query(User).count() == 1
    listing = api_client.get("/api/registration-requests?line_only=true&status=pending", headers=operator_setup[0]).json()
    assert listing["total"] == 1 and listing["items"][0]["request_type"] == "operator_staff"
    assert listing["items"][0]["summary_name"] == "運営 試験" and "line_user_id" not in listing["items"][0]
    response = api_client.post(f"/api/operator-registration/{invitation['request_id']}/approve", json={"user_id": db_session.query(User).filter_by(username="invite-admin").one().id}, headers=operator_setup[0])
    assert response.status_code == 200, response.text
    staff = db_session.query(VanzaiStaff).one()
    assert staff.phone == "09012345678" and not staff.management_roles
    assert db_session.query(User).filter_by(username="invite-admin").one().vanzai_staff_id == staff.id
    assert db_session.query(LineStaffLink).one().staff_id == staff.id
    assert db_session.query(User).count() == 1 and db_session.query(Worker).count() == 0
    assert api_client.get("/api/registration-requests?line_only=true&status=pending", headers=operator_setup[0]).json()["total"] == 0
    audits = db_session.query(AuditLog).all()
    assert {"operator_registration_invited", "operator_registration_submitted", "operator_registration_approved", "operator_line_linked"} <= {a.action for a in audits}
    for audit in audits:
        assert "09012345678" not in str(audit.after_value) and "U-verified-person" not in str(audit.after_value)


def test_same_invitation_retries_are_idempotent_and_cannot_change_person_or_body(api_client, db_session, operator_setup):
    invitation = invite(api_client, operator_setup)
    first = submit(api_client, invitation)
    assert submit(api_client, invitation).json() == first.json()
    assert submit(api_client, invitation, name="別の氏名").status_code == 409
    assert submit(api_client, invitation, id_token="other-person").status_code == 409
    assert db_session.query(OperatorRegistrationDetail).filter_by(is_open=True).count() == 1


def test_duplicate_invites_for_same_line_cannot_create_second_pending(api_client, operator_setup):
    first, second = invite(api_client, operator_setup), invite(api_client, operator_setup)
    assert submit(api_client, first).status_code == 200
    assert submit(api_client, second).status_code == 409


def test_expired_revoked_and_invalid_invites_are_not_accepted(api_client, db_session, operator_setup):
    expired = invite(api_client, operator_setup)
    row = db_session.get(RegistrationRequest, expired["request_id"]); row.expires_at = now() - timedelta(seconds=1); db_session.commit()
    assert submit(api_client, expired).status_code == 410
    revoked = invite(api_client, operator_setup)
    assert api_client.post(f"/api/operator-registration/{revoked['request_id']}/revoke", headers=operator_setup[0]).status_code == 200
    assert submit(api_client, revoked).status_code == 410
    assert submit(api_client, {"token": "unknown-token-value-of-32-characters"}).status_code == 404


def test_invalid_line_proof_and_nonfriend_never_persist_application(api_client, db_session, operator_setup, monkeypatch):
    invitation = invite(api_client, operator_setup)
    def bad(*args): raise LineIdTokenError()
    monkeypatch.setattr("src.api.operator_registration_routes.verify_id_token", bad)
    assert submit(api_client, invitation).status_code == 401
    monkeypatch.setattr("src.api.operator_registration_routes.verify_id_token", lambda *args: "U-person")
    monkeypatch.setattr(operator_setup[1], "profile_name", lambda subject: None)
    assert submit(api_client, invitation).status_code == 409
    assert db_session.get(RegistrationRequest, invitation["request_id"]).status == "link_issued"


@pytest.mark.parametrize("role", ["ops", "accounting", "site_manager", "worker"])
def test_admin_actions_and_phone_detail_are_admin_only(api_client, db_session, operator_setup, role):
    invitation = invite(api_client, operator_setup)
    assert submit(api_client, invitation).status_code == 200
    user = create_user_with_hashed_password(db=db_session, username=role, email=f"{role}@example.test", password="test-password", role=role)
    db_session.commit()
    headers = {"Authorization": "Bearer " + create_access_token({"sub": user.username})}
    for method, path, body in [("post", "/invitations", None), ("get", f"/{invitation['request_id']}", None), ("post", f"/{invitation['request_id']}/approve", {}), ("post", f"/{invitation['request_id']}/reject", {"reason": "test"})]:
        response = api_client.request(method, "/api/operator-registration" + path, json=body, headers=headers)
        assert response.status_code == 403


def test_approval_existing_staff_preserves_profile_and_rejects_stale_revision(api_client, db_session, operator_setup):
    staff = VanzaiStaff(id=generate_ulid(), name="運営 試験", phone="0311112222", email="existing@example.test", management_roles=["現場管理"], is_active=True, profile_revision=3)
    db_session.add(staff); db_session.commit()
    invitation = invite(api_client, operator_setup); assert submit(api_client, invitation).status_code == 200
    path = f"/api/operator-registration/{invitation['request_id']}/approve"
    assert api_client.post(path, json={}, headers=operator_setup[0]).status_code == 409
    assert api_client.post(path, json={"staff_id": staff.id, "profile_revision": 2, "user_id": db_session.query(User).filter_by(username="invite-admin").one().id}, headers=operator_setup[0]).status_code == 409
    assert api_client.post(path, json={"staff_id": staff.id, "profile_revision": 3, "user_id": db_session.query(User).filter_by(username="invite-admin").one().id}, headers=operator_setup[0]).status_code == 200
    db_session.refresh(staff)
    assert staff.phone == "0311112222" and staff.profile_revision == 3 and staff.management_roles == ["現場管理"]
    assert db_session.query(VanzaiStaff).count() == 1
    assert api_client.post(path, json={"staff_id": staff.id, "profile_revision": 3, "user_id": db_session.query(User).filter_by(username="invite-admin").one().id}, headers=operator_setup[0]).status_code == 409


def test_rejection_keeps_history_and_does_not_allow_generic_approval_bypass(api_client, db_session, operator_setup):
    invitation = invite(api_client, operator_setup); assert submit(api_client, invitation).status_code == 200
    for suffix, body in [("approve", {}), ("reject", {"reason": "test"})]:
        assert api_client.post(f"/api/registration-requests/{invitation['request_id']}/{suffix}", json=body, headers=operator_setup[0]).status_code == 409
    response = api_client.post(f"/api/operator-registration/{invitation['request_id']}/reject", json={"reason": "本人確認待ち"}, headers=operator_setup[0])
    assert response.status_code == 200
    assert db_session.get(OperatorRegistrationDetail, invitation["request_id"]).name == "運営 試験"
    assert not db_session.get(OperatorRegistrationDetail, invitation["request_id"]).is_open
    assert db_session.query(LineStaffLink).count() == 0


def test_disabled_entry_never_issues_invite_or_accepts_submission(api_client, operator_setup, monkeypatch):
    invitation = invite(api_client, operator_setup)
    monkeypatch.setenv("LINE_OPERATOR_REGISTRATION_ENABLED", "false")
    assert not api_client.get("/api/line/operator-registration/entry").json()["enabled"]
    assert api_client.post("/api/operator-registration/invitations", headers=operator_setup[0]).status_code == 409
    assert submit(api_client, invitation).status_code == 403


def test_approval_rechecks_friend_status_and_existing_link_conflicts(api_client, db_session, operator_setup, monkeypatch):
    invitation = invite(api_client, operator_setup); assert submit(api_client, invitation).status_code == 200
    monkeypatch.setattr(operator_setup[1], "profile_name", lambda subject: None)
    assert api_client.post(f"/api/operator-registration/{invitation['request_id']}/approve", json={"user_id": db_session.query(User).filter_by(username="invite-admin").one().id}, headers=operator_setup[0]).status_code == 409
    assert db_session.query(VanzaiStaff).count() == 0


def test_approval_requires_precreated_unlinked_management_id_atomically(api_client, db_session, operator_setup):
    invitation = invite(api_client, operator_setup); assert submit(api_client, invitation).status_code == 200
    path = f"/api/operator-registration/{invitation['request_id']}/approve"
    assert api_client.post(path, json={}, headers=operator_setup[0]).status_code == 409
    assert api_client.post(path, json={"user_id": "missing"}, headers=operator_setup[0]).status_code == 409
    assert db_session.get(RegistrationRequest, invitation["request_id"]).status == "pending"
    assert db_session.query(VanzaiStaff).count() == db_session.query(LineStaffLink).count() == 0
    admin = db_session.query(User).filter_by(username="invite-admin").one()
    view = api_client.get(f"/api/operator-registration/{invitation['request_id']}", headers=operator_setup[0]).json()
    assert [u["id"] for u in view["login_candidates"]] == [admin.id]
    assert api_client.post(path, json={"user_id": admin.id}, headers=operator_setup[0]).status_code == 200
    assert admin.vanzai_staff_id == db_session.query(VanzaiStaff).one().id


@pytest.mark.parametrize("invalid", ["worker", "inactive", "deleted", "other_staff", "worker_link"])
def test_approval_rechecks_selected_login_and_keeps_pending_on_conflict(api_client, db_session, operator_setup, invalid):
    invitation = invite(api_client, operator_setup); assert submit(api_client, invitation).status_code == 200
    login = create_user_with_hashed_password(db=db_session, username="candidate-login", email="candidate@test.example", password="test-password", role="ops")
    if invalid == "worker": login.role = "worker"
    elif invalid == "inactive": login.is_active = False
    elif invalid == "deleted": login.deleted_at = now()
    elif invalid == "other_staff":
        other = VanzaiStaff(name="別の運営", is_active=True); db_session.add(other); db_session.flush(); login.vanzai_staff_id = other.id
    elif invalid == "worker_link":
        worker = Worker(name="稼働者本人", is_active=True); db_session.add(worker); db_session.flush(); login.worker_id = worker.id
    db_session.commit()
    before = db_session.query(VanzaiStaff).count()
    response = api_client.post(f"/api/operator-registration/{invitation['request_id']}/approve", json={"user_id": login.id}, headers=operator_setup[0])
    assert response.status_code == 409
    assert db_session.get(RegistrationRequest, invitation["request_id"]).status == "pending"
    assert db_session.query(VanzaiStaff).count() == before and db_session.query(LineStaffLink).count() == 0

def test_operator_migration_adds_no_changes_to_existing_headers(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    url = "sqlite:///" + (tmp_path / "migration.sqlite").as_posix()
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    engine = create_engine(url)
    # Historical migrations include PostgreSQL-only ALTER CONSTRAINT. Build the
    # unchanged prior schema here, then exercise this migration's actual DDL.
    from src.models.base import Base
    Base.metadata.create_all(engine, tables=[table for table in Base.metadata.sorted_tables if table.name != "operator_registration_details"])
    command.stamp(config, "20261024c001")
    with Session(engine) as session:
        row = RegistrationRequest(id=generate_ulid(), request_type="worker", status="pending", source_type="test", failed_attempts=0)
        session.add(row); session.commit(); row_id = row.id
    command.upgrade(config, "20261026a001")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT status FROM registration_requests WHERE id=:id"), {"id": row_id}).scalar() == "pending"
        assert connection.execute(text("SELECT COUNT(*) FROM operator_registration_details")).scalar() == 0
    command.downgrade(config, "20261024c001")
    command.upgrade(config, "20261026a001")
    with Session(engine) as session:
        row = RegistrationRequest(id=generate_ulid(), request_type="operator_staff", status="link_issued", source_type="line_operator", failed_attempts=0)
        session.add(row); session.flush()
        session.add(OperatorRegistrationDetail(request_id=row.id, is_open=False)); session.commit()
    with pytest.raises(RuntimeError, match="履歴があるため削除できません"):
        command.downgrade(config, "20261024c001")
    engine.dispose()
