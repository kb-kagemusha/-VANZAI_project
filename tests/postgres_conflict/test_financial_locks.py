"""PostgreSQL financial serialization; only rows created here are removed."""
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from src.models.base import generate_ulid
from src.models.master import Client, User
from src.models.transaction import Project, Closing
from src.models.closing_approval import ClosingApprovalRequest
from src.models.transaction import AuditLog
from src.services import closing
from src.services.financial_guards import lock_projects, lock_client_projects, ensure_import_mutable
from src.services.closing_approval import request_operation, approve_operation
from src.exceptions import ValidationException, ClosingViolationException


@pytest.fixture
def financial_fixture(conflict_engine):
    Session = sessionmaker(bind=conflict_engine)
    with Session() as setup:
        client = Client(name="Temporary financial review fixture")
        first = User(username="review_request_" + generate_ulid(), email=generate_ulid()+"@example.com", role="admin", is_active=True)
        second = User(username="review_approve_" + generate_ulid(), email=generate_ulid()+"@example.com", role="admin", is_active=True)
        setup.add_all([client, first, second]); setup.flush()
        project = Project(name="Temporary financial review fixture", client_id=client.id)
        setup.add(project); setup.commit()
        ids = project.id, client.id, first.id, second.id
    try:
        yield Session, ids
    finally:
        with Session() as cleanup:
            requests = cleanup.scalars(select(ClosingApprovalRequest.id).where(ClosingApprovalRequest.project_id == ids[0])).all()
            closings = cleanup.scalars(select(Closing.id).where(Closing.project_id == ids[0])).all()
            # These IDs originate from this fixture, never from a broad site sweep.
            if requests or closings:
                cleanup.query(AuditLog).filter(AuditLog.target_id.in_(requests + closings)).delete(synchronize_session=False)
            cleanup.query(ClosingApprovalRequest).filter_by(project_id=ids[0]).delete()
            cleanup.query(Closing).filter_by(project_id=ids[0]).delete()
            cleanup.query(Project).filter_by(id=ids[0]).delete()
            cleanup.query(Client).filter_by(id=ids[1]).delete()
            cleanup.query(User).filter(User.id.in_(ids[2:])).delete(synchronize_session=False)
            cleanup.commit()


def lock_timeout(exc):
    return getattr(exc.orig, "sqlstate", None) == "55P03" or getattr(exc.orig, "pgcode", None) == "55P03"


def test_csv_waits_for_close_then_refuses_closed_period(financial_fixture):
    Session, ids = financial_fixture
    with Session() as holder, Session() as waiter:
        closing.soft_close(holder, ids[0], "202610", "fixture-requester")
        waiter.execute(text("SET lock_timeout = '400ms'"))
        with pytest.raises(OperationalError) as caught:
            ensure_import_mutable(waiter, ids[0], "202610")
        assert lock_timeout(caught.value)
        waiter.rollback(); holder.commit()
        with pytest.raises(ValidationException): ensure_import_mutable(waiter, ids[0], "202610")
        waiter.rollback()


def test_document_generation_uses_same_project_locks(financial_fixture):
    Session, ids = financial_fixture
    with Session() as holder, Session() as waiter:
        lock_projects(holder, [ids[0]])
        waiter.execute(text("SET lock_timeout = '400ms'"))
        with pytest.raises(OperationalError) as caught: lock_client_projects(waiter, ids[1])
        assert lock_timeout(caught.value)
        waiter.rollback(); holder.commit()
        lock_client_projects(waiter, ids[1])
        waiter.rollback()


def test_only_one_authenticated_approval_completes(financial_fixture):
    Session, ids = financial_fixture
    with Session() as setup:
        closing.soft_close(setup, ids[0], "202610", "fixture-requester")
        request = request_operation(setup, ids[0], "202610", "soft_release", setup.get(User, ids[2]), "temporary review")
        request_id = request.id; setup.commit()
    with Session() as holder, Session() as waiter:
        result = approve_operation(holder, request_id, holder.get(User, ids[3]))
        assert result.release_count == 1
        waiter.execute(text("SET lock_timeout = '400ms'"))
        with pytest.raises(OperationalError) as caught: approve_operation(waiter, request_id, waiter.get(User, ids[3]))
        assert lock_timeout(caught.value)
        waiter.rollback(); holder.commit()
        with pytest.raises(ClosingViolationException): approve_operation(waiter, request_id, waiter.get(User, ids[3]))
        waiter.rollback()
