"""試験用PostgreSQLでの制約と、通常の稼働者編集の同時保存。

LINE承認の競合試験（T09、T13、T14、T15）ではない。
この試験が挿入した申請と稼働者だけを削除する。
"""
import threading

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.domain.worker_edit_guard import (
    WorkerEditGuardError,
    issue_worker_edit_guard,
    lock_worker_for_edit,
    verify_worker_edit_guard,
)
from src.models.master import Worker

WORKER_ID = "01CONFLICTWORKER0000000001"
EDITOR_A = "01EDITORA0000000000000001"
EDITOR_B = "01EDITORB0000000000000001"


def _insert_request(connection, request_id: str) -> None:
    connection.execute(
        text(
            """
            INSERT INTO registration_requests (id, request_type, status, source_type)
            VALUES (:id, 'worker', 'pending', 'public_form')
            """
        ),
        {"id": request_id},
    )


def test_constraints_reject_invalid_registration_rows(conflict_engine):
    request_a = "01REQCONFLICT000000000001"
    request_b = "01REQCONFLICT000000000002"
    request_c = "01REQCONFLICT000000000003"
    with conflict_engine.begin() as connection:
        connection.execute(
            text("DELETE FROM line_registration_submit_keys WHERE id LIKE '01KEYCONFLICT%'")
        )
        connection.execute(
            text("DELETE FROM line_registration_contexts WHERE id LIKE '01CTXCONFLICT%'")
        )
        connection.execute(
            text("DELETE FROM line_registration_sessions WHERE id LIKE '01SESSCONFLICT%'")
        )
        connection.execute(
            text("DELETE FROM registration_requests WHERE id IN (:a, :b, :c)"),
            {"a": request_a, "b": request_b, "c": request_c},
        )
        _insert_request(connection, request_a)
        _insert_request(connection, request_b)
        _insert_request(connection, request_c)

    def insert(sql: str, params: dict | None = None) -> None:
        with conflict_engine.begin() as connection:
            connection.execute(text(sql), params or {})

    with pytest.raises(IntegrityError):
        insert(
            """
            INSERT INTO line_registration_sessions
                (id, token_hash, line_user_id, expires_at)
            VALUES ('01SESSCONFLICT00000000001', repeat('b', 64), '', now())
            """
        )
    with pytest.raises(IntegrityError):
        insert(
            """
            INSERT INTO line_registration_sessions
                (id, token_hash, line_user_id, expires_at)
            VALUES ('01SESSCONFLICT00000000002', repeat('c', 10), 'subject-hash', now())
            """
        )
    insert(
        """
        INSERT INTO line_registration_contexts
            (id, request_id, line_user_id, is_open)
        VALUES ('01CTXCONFLICT000000000001', :request_id, 'subject-open', true)
        """,
        {"request_id": request_a},
    )
    with pytest.raises(IntegrityError):
        insert(
            """
            INSERT INTO line_registration_contexts
                (id, request_id, line_user_id, is_open)
            VALUES ('01CTXCONFLICT000000000002', :request_id, 'subject-open', true)
            """,
            {"request_id": request_b},
        )
    insert(
        """
        INSERT INTO line_registration_contexts
            (id, request_id, line_user_id, is_open)
        VALUES
            ('01CTXCONFLICT000000000003', :request_b, 'subject-closed', false),
            ('01CTXCONFLICT000000000004', :request_c, 'subject-closed', false)
        """,
        {"request_b": request_b, "request_c": request_c},
    )
    insert(
        """
        INSERT INTO line_registration_submit_keys
            (id, line_user_id, idempotency_key, request_id, content_hash)
        VALUES
            ('01KEYCONFLICT000000000001', 'subject-key', 'same-key', :request_id, repeat('d', 64))
        """,
        {"request_id": request_a},
    )
    with pytest.raises(IntegrityError):
        insert(
            """
            INSERT INTO line_registration_submit_keys
                (id, line_user_id, idempotency_key, request_id, content_hash)
            VALUES
                ('01KEYCONFLICT000000000002', 'subject-key', 'same-key', :request_id, repeat('e', 64))
            """,
            {"request_id": request_b},
        )
    with pytest.raises(IntegrityError):
        insert(
            """
            INSERT INTO line_registration_submit_keys
                (id, line_user_id, idempotency_key, request_id, content_hash)
            VALUES
                ('01KEYCONFLICT000000000003', 'subject-key', '', :request_id, repeat('f', 64))
            """,
            {"request_id": request_c},
        )
    with pytest.raises(IntegrityError):
        insert(
            """
            INSERT INTO line_registration_submit_keys
                (id, line_user_id, idempotency_key, request_id, content_hash)
            VALUES
                ('01KEYCONFLICT000000000004', 'subject-key', 'other-key', :request_id, repeat('g', 8))
            """,
            {"request_id": request_c},
        )

    with conflict_engine.begin() as connection:
        connection.execute(text("DELETE FROM line_registration_submit_keys WHERE line_user_id = 'subject-key'"))
        connection.execute(text("DELETE FROM line_registration_contexts WHERE line_user_id IN ('subject-open', 'subject-closed')"))
        connection.execute(
            text("DELETE FROM registration_requests WHERE id IN (:a, :b, :c)"),
            {"a": request_a, "b": request_b, "c": request_c},
        )


def test_concurrent_worker_edits_keep_the_winning_update(conflict_engine):
    """同時保存では片方だけが成功し、失敗側の値では上書きされない。"""
    Session = sessionmaker(bind=conflict_engine)
    setup = Session()
    try:
        existing = setup.get(Worker, WORKER_ID)
        if existing is not None:
            setup.delete(existing)
            setup.commit()
        setup.add(Worker(id=WORKER_ID, name="同時保存前", phone="08000000000", is_active=True, tags=[]))
        setup.commit()
        worker = setup.get(Worker, WORKER_ID)
        ticket_a = issue_worker_edit_guard(worker, EDITOR_A)
        ticket_b = issue_worker_edit_guard(worker, EDITOR_B)
    finally:
        setup.close()

    ready = threading.Barrier(2)
    outcomes: list[tuple[str, str]] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def attempt(editor_id: str, ticket: str, phone: str) -> None:
        db = Session()
        try:
            db.execute(text("SET lock_timeout = '10s'"))
            ready.wait(timeout=10)
            current = lock_worker_for_edit(db, WORKER_ID)
            verify_worker_edit_guard(ticket, current, editor_id)
            current.phone = phone
            db.commit()
            with lock:
                outcomes.append(("ok", phone))
        except WorkerEditGuardError:
            db.rollback()
            with lock:
                outcomes.append(("conflict", phone))
        except BaseException as exc:
            db.rollback()
            with lock:
                errors.append(exc)
        finally:
            db.close()

    first = threading.Thread(target=attempt, args=(EDITOR_A, ticket_a, "09000000001"))
    second = threading.Thread(target=attempt, args=(EDITOR_B, ticket_b, "09000000002"))
    first.start()
    second.start()
    first.join()
    second.join()

    check = Session()
    try:
        assert errors == []
        assert sorted(kind for kind, _phone in outcomes) == ["conflict", "ok"]
        winner = next(phone for kind, phone in outcomes if kind == "ok")
        saved = check.get(Worker, WORKER_ID)
        assert saved is not None
        assert saved.phone == winner
        assert saved.name == "同時保存前"
    finally:
        saved = check.get(Worker, WORKER_ID)
        if saved is not None:
            check.delete(saved)
            check.commit()
        check.close()
