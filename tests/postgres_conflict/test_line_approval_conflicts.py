"""PostgreSQLでのLINE承認の競合。

送信、承認、解除、通常編集が、申請、稼働者、紐付けの順で待つことを確認する。
受付の同時送信試験ではない。この試験が作った行だけを消す。
"""
import threading
from datetime import datetime, timezone

import pytest
from sqlalchemy import bindparam, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from src.domain.worker_edit_guard import WorkerEditGuardError, issue_worker_edit_guard, lock_worker_for_edit, verify_worker_edit_guard
from src.models.line_order import LINK_ACTIVE
from src.models.master import User
from src.services.line_order import LineOrderService
from src.services.line_registration import LineRegistrationService
from src.services.line_registration_review import LineRegistrationReviewService, LineReviewError

LINE_USER = "U-approve-conflict"
WORKER_ID = "01APPRVCONFLICTWORKER00001"
LINK_ID = "01APPRVCONFLICTLINK0000001"
REVIEWER_ID = "01APPROVER0000000000000001"


def _enable(monkeypatch) -> None:
    monkeypatch.setenv("LINE_WORKER_REGISTRATION_ENABLED", "1")
    monkeypatch.setenv("LINE_LIFF_ID", "liff-test")
    monkeypatch.setenv("LINE_LOGIN_CHANNEL_ID", "login-channel")
    monkeypatch.setenv("WORKER_EDIT_GUARD_KEY", "line-approval-conflict-test")


def _body(phone: str = "09000001111") -> dict:
    return {
        "last_name": "山田",
        "first_name": "太郎",
        "last_name_furigana": "やまだ",
        "first_name_furigana": "たろう",
        "phone": phone,
        "birth_date": "1990-01-02",
        "postal_code": "1000001",
        "prefecture": "東京都",
        "address1": "千代田区1-1",
        "address2": "",
    }


def _cleanup(connection) -> None:
    request_ids = [
        row[0]
        for row in connection.execute(
            text(
                """
                SELECT request_id FROM line_registration_contexts WHERE line_user_id = :user
                UNION
                SELECT request_id FROM line_registration_submit_keys WHERE line_user_id = :user
                """
            ),
            {"user": LINE_USER},
        )
    ]
    worker_ids = [WORKER_ID]
    if request_ids:
        worker_ids.extend(
            row[0]
            for row in connection.execute(
                text(
                    "SELECT approved_target_id FROM registration_requests WHERE id IN :ids AND approved_target_id IS NOT NULL"
                ).bindparams(bindparam("ids", expanding=True)),
                {"ids": request_ids},
            )
            if row[0]
        )
    connection.execute(
        text("DELETE FROM line_registration_submit_keys WHERE line_user_id = :user"),
        {"user": LINE_USER},
    )
    connection.execute(
        text("DELETE FROM line_registration_contexts WHERE line_user_id = :user"),
        {"user": LINE_USER},
    )
    connection.execute(
        text("DELETE FROM line_registration_sessions WHERE line_user_id = :user"),
        {"user": LINE_USER},
    )
    if request_ids:
        for statement in (
            "DELETE FROM worker_registration_request_details WHERE request_id IN :ids",
            "DELETE FROM audit_logs WHERE target_id IN :ids",
            "DELETE FROM registration_requests WHERE id IN :ids",
        ):
            connection.execute(
                text(statement).bindparams(bindparam("ids", expanding=True)),
                {"ids": request_ids},
            )
    connection.execute(
        text("DELETE FROM line_worker_links WHERE line_user_id = :user OR id = :link OR worker_id IN :workers").bindparams(
            bindparam("workers", expanding=True)
        ),
        {"user": LINE_USER, "link": LINK_ID, "workers": worker_ids},
    )
    connection.execute(
        text("DELETE FROM workers WHERE id IN :workers").bindparams(bindparam("workers", expanding=True)),
        {"workers": worker_ids},
    )
    connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": REVIEWER_ID})


def _is_lock_timeout(exc: OperationalError) -> bool:
    origin = getattr(exc, "orig", None)
    sqlstate = getattr(origin, "sqlstate", None) or getattr(origin, "pgcode", None)
    return sqlstate == "55P03" or "lock timeout" in f"{origin or ''} {exc}".lower()


@pytest.fixture
def approval_sessions(conflict_engine, monkeypatch):
    _enable(monkeypatch)
    Session = sessionmaker(bind=conflict_engine)

    def sweep() -> None:
        db = Session()
        try:
            db.rollback()
            _cleanup(db)
            db.commit()
        finally:
            db.close()

    sweep()
    yield Session
    sweep()


def _prepare(Session):
    from src.models.line_order import LineWorkerLink
    from src.models.master import User, Worker

    setup = Session()
    try:
        with setup.begin():
            _cleanup(setup)
        reviewer = User(
            id=REVIEWER_ID,
            username="approve_conflict_admin",
            email="approve-conflict@example.com",
            role="admin",
            is_active=True,
        )
        worker = Worker(id=WORKER_ID, name="承認前", phone="09000000000", email="keep@example.com", nearest_station="旧駅", station_walk_minutes=10, is_active=True, tags=[])
        link = LineWorkerLink(
            id=LINK_ID,
            worker_id=WORKER_ID,
            line_user_id=LINE_USER,
            status=LINK_ACTIVE,
            linked_at=datetime.now(timezone.utc),
        )
        setup.add(reviewer)
        setup.add(worker)
        setup.flush()
        setup.add(link)
        setup.flush()
        setup.commit()
        token, _expires, linked, _tag = LineRegistrationService(setup).issue_session(LINE_USER)
        assert linked is True
        body = {"phone": "09000001111", "nearest_station": "新宿駅", "station_walk_minutes": "0"}
        result = LineRegistrationService(setup).submit(token, "approve-key", body, set(body))
        setup.commit()
        review = LineRegistrationReviewService(setup).view(result.request_id, reviewer)
        edit_ticket = issue_worker_edit_guard(worker, reviewer.id)
        return result.request_id, review["comparison_ticket"], edit_ticket, token
    finally:
        setup.close()


def _until(engine, predicate) -> bool:
    connection = engine.connect()
    try:
        deadline = connection.execute(text("SELECT clock_timestamp() + interval '8 seconds'")).scalar()
        while connection.execute(text("SELECT clock_timestamp() < :deadline"), {"deadline": deadline}).scalar():
            if predicate(connection):
                return True
        return False
    finally:
        connection.close()


def _waiting_while_holding(connection, waiting_table: str, held_table: str) -> bool:
    pid = connection.execute(
        text(
            """
            SELECT a.pid
            FROM pg_stat_activity a
            JOIN pg_locks held ON held.pid = a.pid AND held.granted
            JOIN pg_class held_class ON held_class.oid = held.relation
            WHERE a.pid <> pg_backend_pid()
              AND a.wait_event_type = 'Lock'
              AND a.query LIKE :waiting
              AND held_class.relname = :held
            LIMIT 1
            """
        ),
        {"waiting": f"%{waiting_table}%", "held": held_table},
    ).scalar()
    return pid is not None


@pytest.mark.parametrize("changed_field", ["phone", "nearest_station", "station_walk_minutes"])
def test_approve_holds_the_request_while_waiting_for_the_worker(approval_sessions, conflict_engine, changed_field):
    request_id, ticket, _edit, _token = _prepare(approval_sessions)
    holder = conflict_engine.connect()
    transaction = holder.begin()
    holder.execute(text("SELECT id FROM workers WHERE id = :id FOR UPDATE"), {"id": WORKER_ID})
    outcome = []
    started = threading.Event()

    def approve() -> None:
        connection = conflict_engine.connect()
        db = approval_sessions(bind=connection)
        try:
            db.execute(text("SET lock_timeout = '15s'"))
            started.set()
            reviewer = db.get(User, REVIEWER_ID)
            LineRegistrationReviewService(db).approve(request_id, ticket, reviewer)
            db.commit()
            outcome.append("ok")
        except LineReviewError as exc:
            db.rollback()
            outcome.append(exc.category)
        except BaseException as exc:
            db.rollback()
            outcome.append(type(exc).__name__)
        finally:
            db.close()
            connection.close()

    thread = threading.Thread(target=approve)
    thread.start()
    assert started.wait(5), outcome
    try:
        observed = _until(
            conflict_engine,
            lambda connection: _waiting_while_holding(connection, "workers", "registration_requests"),
        )
        values = {"phone": "09000000099", "nearest_station": "別の管理者の駅", "station_walk_minutes": 99}
        holder.execute(text(f"UPDATE workers SET {changed_field} = :value WHERE id = :id"), {"id": WORKER_ID, "value": values[changed_field]})
        transaction.commit()
    finally:
        if transaction.is_active:
            transaction.rollback()
        holder.close()
        thread.join(timeout=20)
    assert not thread.is_alive()
    assert observed, outcome
    check = approval_sessions()
    try:
        assert outcome == ["ticket_mismatch"]
        phone = check.execute(text("SELECT phone FROM workers WHERE id = :id"), {"id": WORKER_ID}).scalar_one()
        status = check.execute(text("SELECT status FROM registration_requests WHERE id = :id"), {"id": request_id}).scalar_one()
        assert phone == ("09000000099" if changed_field == "phone" else "09000000000")
        station = check.execute(text("SELECT nearest_station, station_walk_minutes FROM workers WHERE id = :id"), {"id": WORKER_ID}).one()
        assert station.nearest_station == ("別の管理者の駅" if changed_field == "nearest_station" else "旧駅")
        assert station.station_walk_minutes == (99 if changed_field == "station_walk_minutes" else 10)
        assert status == "pending"
    finally:
        check.rollback()
        check.close()


def test_approve_waits_for_the_link_then_refuses_the_revoked_row(approval_sessions, conflict_engine):
    request_id, ticket, _edit, _token = _prepare(approval_sessions)
    holder = conflict_engine.connect()
    transaction = holder.begin()
    holder.execute(text("SELECT id FROM line_worker_links WHERE id = :id FOR UPDATE"), {"id": LINK_ID})
    blocked = approval_sessions()
    try:
        blocked.execute(text("SET lock_timeout = '400ms'"))
        reviewer = blocked.get(User, REVIEWER_ID)
        with pytest.raises(OperationalError) as caught:
            LineRegistrationReviewService(blocked).approve(request_id, ticket, reviewer)
        assert _is_lock_timeout(caught.value)
        blocked.rollback()
    finally:
        blocked.close()
    holder.execute(
        text("UPDATE line_worker_links SET status = 'revoked', revoked_at = now() WHERE id = :id"),
        {"id": LINK_ID},
    )
    transaction.commit()
    holder.close()

    retry = approval_sessions()
    try:
        reviewer = retry.get(User, REVIEWER_ID)
        with pytest.raises(LineReviewError) as refused:
            LineRegistrationReviewService(retry).approve(request_id, ticket, reviewer)
        assert refused.value.category in {"fixed_target", "link_changed", "ticket_mismatch"}
        retry.rollback()
        phone = retry.execute(text("SELECT phone FROM workers WHERE id = :id"), {"id": WORKER_ID}).scalar_one()
        status = retry.execute(text("SELECT status FROM registration_requests WHERE id = :id"), {"id": request_id}).scalar_one()
        assert phone == "09000000000"
        assert status == "pending"
    finally:
        retry.close()


def test_submit_approve_unlink_and_edit_keep_one_result(approval_sessions, conflict_engine):
    request_id, ticket, edit_ticket, token = _prepare(approval_sessions)
    ready = threading.Barrier(4)
    outcome = []
    lock = threading.Lock()

    def record(kind: str, detail: str) -> None:
        with lock:
            outcome.append((kind, detail))

    def approve() -> None:
        db = approval_sessions()
        try:
            db.execute(text("SET lock_timeout = '15s'"))
            ready.wait(timeout=10)
            reviewer = db.get(User, REVIEWER_ID)
            LineRegistrationReviewService(db).approve(request_id, ticket, reviewer)
            db.commit()
            record("approve", "ok")
        except LineReviewError as exc:
            db.rollback()
            record("approve", exc.category)
        except BaseException as exc:
            db.rollback()
            record("approve", type(exc).__name__)
        finally:
            db.close()

    def submit() -> None:
        db = approval_sessions()
        try:
            db.execute(text("SET lock_timeout = '15s'"))
            ready.wait(timeout=10)
            result = LineRegistrationService(db).submit(token, "approve-other", {"phone": "09000002222"}, {"phone"})
            db.commit()
            record("submit", result.request_id)
        except BaseException as exc:
            db.rollback()
            record("submit", type(exc).__name__)
        finally:
            db.close()

    def edit() -> None:
        db = approval_sessions()
        try:
            db.execute(text("SET lock_timeout = '15s'"))
            ready.wait(timeout=10)
            worker = lock_worker_for_edit(db, WORKER_ID)
            verify_worker_edit_guard(edit_ticket, worker, REVIEWER_ID)
            worker.phone = "09000000077"
            db.commit()
            record("edit", "ok")
        except WorkerEditGuardError:
            db.rollback()
            record("edit", "conflict")
        except BaseException as exc:
            db.rollback()
            record("edit", type(exc).__name__)
        finally:
            db.close()

    def unlink() -> None:
        db = approval_sessions()
        try:
            db.execute(text("SET lock_timeout = '15s'"))
            ready.wait(timeout=10)
            reviewer = db.get(User, REVIEWER_ID)
            LineOrderService(db).revoke_link(actor=reviewer, worker_id=WORKER_ID, reason="試験の解除")
            db.commit()
            record("unlink", "ok")
        except BaseException as exc:
            db.rollback()
            record("unlink", type(exc).__name__)
        finally:
            db.close()

    threads = [threading.Thread(target=item) for item in (approve, submit, edit, unlink)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=25)
    assert all(not thread.is_alive() for thread in threads)

    check = approval_sessions()
    try:
        kinds = {kind for kind, _detail in outcome}
        assert kinds == {"approve", "submit", "edit", "unlink"}
        status = check.execute(text("SELECT status FROM registration_requests WHERE id = :id"), {"id": request_id}).scalar_one()
        phone = check.execute(text("SELECT phone FROM workers WHERE id = :id"), {"id": WORKER_ID}).scalar_one()
        link_status = check.execute(text("SELECT status FROM line_worker_links WHERE id = :id"), {"id": LINK_ID}).scalar_one()
        approve_detail = next(detail for kind, detail in outcome if kind == "approve")
        unlink_detail = next(detail for kind, detail in outcome if kind == "unlink")
        if approve_detail == "ok":
            assert status == "approved"
            assert phone == "09000001111"
            station = check.execute(text("SELECT nearest_station, station_walk_minutes FROM workers WHERE id = :id"), {"id": WORKER_ID}).one()
            assert tuple(station) == ("新宿駅", 0)
        else:
            assert status == "pending"
            assert approve_detail in {"ticket_mismatch", "link_changed", "fixed_target"}
            assert phone in {"09000000000", "09000000077"}
        if unlink_detail == "ok":
            assert link_status == "revoked"
        assert not any(detail == "OperationalError" for _kind, detail in outcome)
    finally:
        check.rollback()
        check.close()
