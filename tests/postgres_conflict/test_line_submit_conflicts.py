"""PostgreSQLでのLINE申請送信の競合。

同時送信、同じキー、紐付け解除を、独立した接続で確認する。
LINE承認の競合試験ではない。この試験が作った行だけを消す。
"""
import threading
from datetime import datetime, timezone

import pytest
from sqlalchemy import bindparam, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from src.models.line_order import LineWorkerLink
from src.models.line_registration import LineRegistrationContext
from src.models.master import Worker
from src.services.line_registration import (
    NOT_SAVED_MESSAGE,
    SAVED_MESSAGE,
    LineRegistrationRejected,
    LineRegistrationService,
)

LINE_USER = "U-submit-conflict"
OTHER_USER = "U-submit-conflict-key"
LINK_USER = "U-submit-conflict-link"
WORKER_ID = "01SUBMITCONFLICTWORKER0001"
LINK_ID = "01SUBMITCONFLICTLINK000001"


def _enable(monkeypatch) -> None:
    monkeypatch.setenv("LINE_WORKER_REGISTRATION_ENABLED", "1")
    monkeypatch.setenv("LINE_LIFF_ID", "liff-test")
    monkeypatch.setenv("LINE_LOGIN_CHANNEL_ID", "login-channel")
    monkeypatch.setenv("WORKER_EDIT_GUARD_KEY", "line-submit-conflict-test")


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
        "nearest_station": "試験用駅",
        "station_walk_minutes": "0",
        "email": "worker@example.com",
        "emergency_contact_phone": "09000002222",
        "emergency_contact_name": "山田 花子",
        "emergency_contact_relationship": "実母",
    }


def _sent() -> set[str]:
    return set(_body())


def _users() -> dict[str, str]:
    return {"a": LINE_USER, "b": OTHER_USER, "c": LINK_USER}


def _cleanup(connection) -> None:
    users = _users()
    request_ids = [
        row[0]
        for row in connection.execute(
            text(
                """
                SELECT request_id FROM line_registration_contexts
                WHERE line_user_id IN (:a, :b, :c)
                UNION
                SELECT request_id FROM line_registration_submit_keys
                WHERE line_user_id IN (:a, :b, :c)
                """
            ),
            users,
        )
    ]
    connection.execute(
        text("DELETE FROM line_registration_submit_keys WHERE line_user_id IN (:a, :b, :c)"),
        users,
    )
    connection.execute(
        text("DELETE FROM line_registration_contexts WHERE line_user_id IN (:a, :b, :c)"),
        users,
    )
    connection.execute(
        text("DELETE FROM line_registration_sessions WHERE line_user_id IN (:a, :b, :c)"),
        users,
    )
    if request_ids:
        for statement in (
            "DELETE FROM worker_registration_request_details WHERE request_id IN :ids",
            "DELETE FROM audit_logs WHERE target_id IN :ids AND actor = 'line-registration'",
            "DELETE FROM registration_requests WHERE id IN :ids",
        ):
            connection.execute(
                text(statement).bindparams(bindparam("ids", expanding=True)),
                {"ids": request_ids},
            )
    connection.execute(text("DELETE FROM line_worker_links WHERE id = :id OR worker_id = :worker"), {"id": LINK_ID, "worker": WORKER_ID})
    connection.execute(text("DELETE FROM workers WHERE id = :id"), {"id": WORKER_ID})


def _is_lock_timeout(exc: OperationalError) -> bool:
    origin = getattr(exc, "orig", None)
    sqlstate = getattr(origin, "sqlstate", None) or getattr(origin, "pgcode", None)
    if sqlstate == "55P03":
        return True
    message = f"{origin or ''} {exc}".lower()
    return "lock timeout" in message


@pytest.fixture
def submit_sessions(conflict_engine, monkeypatch):
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


def test_concurrent_submits_keep_one_request(submit_sessions):
    Session = submit_sessions
    setup = Session()
    try:
        with setup.begin():
            _cleanup(setup)
        token, _expires, linked, _tag = LineRegistrationService(setup).issue_session(LINE_USER)
        assert linked is False
        setup.commit()
    finally:
        setup.close()

    ready = threading.Barrier(2)
    results = []
    errors = []
    lock = threading.Lock()

    def attempt(key: str) -> None:
        db = Session()
        try:
            db.execute(text("SET lock_timeout = '10s'"))
            ready.wait(timeout=10)
            result = LineRegistrationService(db).submit(token, key, _body(), _sent())
            db.commit()
            with lock:
                results.append(result)
        except BaseException as exc:
            db.rollback()
            with lock:
                errors.append(exc)
        finally:
            db.close()

    first = threading.Thread(target=attempt, args=("key-one",))
    second = threading.Thread(target=attempt, args=("key-two",))
    first.start()
    second.start()
    first.join()
    second.join()

    check = Session()
    try:
        assert errors == []
        assert {item.request_id for item in results} == {results[0].request_id}
        assert sorted(item.saved for item in results) == [False, True]
        assert any(item.message == NOT_SAVED_MESSAGE and item.saved is False for item in results)
        assert check.query(LineRegistrationContext).filter_by(line_user_id=LINE_USER).count() == 1
    finally:
        check.rollback()
        _cleanup(check)
        check.commit()
        check.close()


def test_same_key_conflict_keeps_the_first_body(submit_sessions):
    Session = submit_sessions
    setup = Session()
    try:
        with setup.begin():
            _cleanup(setup)
        token, _expires, _linked, _tag = LineRegistrationService(setup).issue_session(OTHER_USER)
        setup.commit()
    finally:
        setup.close()

    ready = threading.Barrier(2)
    outcomes = []
    errors = []
    lock = threading.Lock()

    def attempt(phone: str) -> None:
        db = Session()
        try:
            db.execute(text("SET lock_timeout = '10s'"))
            ready.wait(timeout=10)
            result = LineRegistrationService(db).submit(token, "same-key", _body(phone), _sent())
            db.commit()
            with lock:
                outcomes.append(("ok", phone, result.request_id))
        except LineRegistrationRejected as exc:
            db.rollback()
            with lock:
                outcomes.append(("conflict", phone, exc.status_code))
        except BaseException as exc:
            db.rollback()
            with lock:
                errors.append(exc)
        finally:
            db.close()

    first = threading.Thread(target=attempt, args=("09000000001",))
    second = threading.Thread(target=attempt, args=("09000000002",))
    first.start()
    second.start()
    first.join()
    second.join()

    check = Session()
    try:
        assert errors == []
        assert sorted(kind for kind, _phone, _extra in outcomes) == ["conflict", "ok"]
        winner = next(phone for kind, phone, _extra in outcomes if kind == "ok")
        detail_phone = check.execute(
            text(
                """
                SELECT phone FROM worker_registration_request_details
                WHERE request_id IN (
                    SELECT request_id FROM line_registration_contexts WHERE line_user_id = :user
                )
                """
            ),
            {"user": OTHER_USER},
        ).scalar_one()
        assert detail_phone == winner
        replay = LineRegistrationService(check).submit(token, "same-key", _body(winner), _sent())
        assert replay.message == SAVED_MESSAGE
        mismatch = None
        try:
            LineRegistrationService(check).submit(token, "same-key", _body("09000000009"), _sent())
        except LineRegistrationRejected as exc:
            mismatch = exc
        assert mismatch is not None and mismatch.status_code == 409
    finally:
        check.rollback()
        _cleanup(check)
        check.commit()
        check.close()


def test_new_submit_waits_for_link_revocation_and_does_not_save(submit_sessions, conflict_engine):
    Session = submit_sessions
    setup = Session()
    try:
        with setup.begin():
            _cleanup(setup)
        setup.add(Worker(id=WORKER_ID, name="解除前", is_active=True, tags=[]))
        setup.flush()
        setup.add(
            LineWorkerLink(
                id=LINK_ID,
                worker_id=WORKER_ID,
                line_user_id=LINK_USER,
                status="active",
                linked_at=datetime.now(timezone.utc),
            )
        )
        setup.flush()
        token, _expires, linked, _tag = LineRegistrationService(setup).issue_session(LINK_USER)
        assert linked is True
        saved = LineRegistrationService(setup).submit(token, "key-saved", {"phone": "09000001111"}, {"phone"})
        setup.commit()
    finally:
        setup.close()

    holder = conflict_engine.connect()
    held = holder.begin()
    holder.execute(text("SELECT id FROM line_worker_links WHERE id = :id FOR UPDATE"), {"id": LINK_ID})
    blocked = Session()
    try:
        blocked.execute(text("SET lock_timeout = '400ms'"))
        with pytest.raises(OperationalError) as caught:
            LineRegistrationService(blocked).submit(token, "key-during-revoke", {"phone": "09000002222"}, {"phone"})
        assert _is_lock_timeout(caught.value)
    finally:
        blocked.rollback()
        blocked.close()
        holder.execute(text("UPDATE line_worker_links SET status = 'revoked' WHERE id = :id"), {"id": LINK_ID})
        held.commit()
        holder.close()

    after = Session()
    try:
        replay = LineRegistrationService(after).submit(token, "key-saved", {"phone": "09000001111"}, {"phone"})
        assert replay.request_id == saved.request_id
        assert replay.saved is True
        with pytest.raises(LineRegistrationRejected) as rejected:
            LineRegistrationService(after).submit(token, "key-after-revoke", {"phone": "09000003333"}, {"phone"})
        assert rejected.value.status_code == 409
        after.rollback()
        stored = after.execute(
            text(
                """
                SELECT phone FROM worker_registration_request_details
                WHERE request_id = :request_id
                """
            ),
            {"request_id": saved.request_id},
        ).scalar_one()
        assert stored == "09000001111"
        assert after.query(LineRegistrationContext).filter_by(line_user_id=LINK_USER).count() == 1
    finally:
        after.rollback()
        _cleanup(after)
        after.commit()
        after.close()
