import json
import pytest
from sqlalchemy import inspect
from scripts.reset_admin_password import preview, reset, target
from src.api.jwt_auth import get_password_hash, verify_password
from src.models.master import User
from src.models.transaction import AuditLog
from tests.test_order_billing import admin_user  # noqa: F401


def test_preview_defers_old_password_and_reset_preserves_identity(db_session, admin_user):
    username, uid = admin_user.username, admin_user.id
    identity = (admin_user.role, admin_user.worker_id, admin_user.vanzai_staff_id, admin_user.is_active)
    db_session.expunge_all()
    current = target(db_session, username)
    info = preview(db_session, username)
    assert "hashed_password" in inspect(current).unloaded
    assert "password" not in json.dumps(info)
    password = "local-test-new-password-123"
    new_hash = get_password_hash(password)
    result = reset(db_session, username, uid, info["token"], new_hash)
    db_session.commit(); db_session.expire_all()
    current = db_session.get(User, uid)
    assert verify_password(password, current.hashed_password)
    assert (current.role, current.worker_id, current.vanzai_staff_id, current.is_active) == identity
    assert result["password_reset"] is True
    log = db_session.query(AuditLog).filter_by(action="admin_password_reset").one()
    assert password not in str(log.after_value) and new_hash not in str(log.after_value)
    with pytest.raises(ValueError):
        reset(db_session, username, uid, info["token"], new_hash)


def test_wrong_identity_role_inactive_and_plaintext_are_refused(db_session, admin_user):
    info = preview(db_session, admin_user.username)
    with pytest.raises(ValueError): reset(db_session, admin_user.username, admin_user.id, info["token"], "plaintext")
    with pytest.raises(ValueError): reset(db_session, admin_user.username, "wrong-id", info["token"], get_password_hash("test-password-123"))
    admin_user.role = "ops"; db_session.commit()
    with pytest.raises(ValueError): preview(db_session, admin_user.username)
    admin_user.role = "admin"; admin_user.is_active = False; db_session.commit()
    with pytest.raises(ValueError): preview(db_session, admin_user.username)
