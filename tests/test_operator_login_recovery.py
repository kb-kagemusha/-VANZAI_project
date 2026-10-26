"""Explicit recovery never guesses a person, steals another identity or changes roles."""
import pytest
from scripts.line.bind_operator_login import bind_existing, BindingError
from tests.test_line_operator_portal import operator  # noqa: F401
from src.models.master import User, VanzaiStaff
from src.models.transaction import AuditLog


def test_preview_has_no_writes_and_explicit_apply_only_sets_existing_user(db_session, operator):
    staff, user, _ = operator
    user.vanzai_staff_id = None; db_session.commit()
    before = db_session.query(AuditLog).count()
    result = bind_existing(db_session, staff.name, user.username)
    assert result["applied"] is False and user.vanzai_staff_id is None
    assert db_session.query(AuditLog).count() == before
    result = bind_existing(db_session, staff.name, user.username, True)
    assert result["applied"] and user.vanzai_staff_id == staff.id and user.role == "ops"
    assert db_session.query(User).count() == 1
    again = bind_existing(db_session, staff.name, user.username, True)
    assert again["already_bound"] and db_session.query(AuditLog).count() == before + 1


@pytest.mark.parametrize("problem", ["worker", "inactive", "other_staff", "duplicate_name", "missing_login"])
def test_conflicts_are_not_modified(db_session, operator, problem):
    staff, user, _ = operator
    user.vanzai_staff_id = None
    username = user.username
    if problem == "worker": user.role = "worker"
    elif problem == "inactive": user.is_active = False
    elif problem == "other_staff":
        other = VanzaiStaff(name="別人", is_active=True); db_session.add(other); db_session.flush(); user.vanzai_staff_id = other.id
    elif problem == "duplicate_name": db_session.add(VanzaiStaff(name=staff.name, is_active=True))
    else: username = "missing"
    db_session.commit(); before = user.vanzai_staff_id
    with pytest.raises(BindingError): bind_existing(db_session, staff.name, username, True)
    assert user.vanzai_staff_id == before
