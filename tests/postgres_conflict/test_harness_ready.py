"""試験用PostgreSQLの競合試験基盤。

このファイルが通ることは、独立した2接続で行ロックを確認できたことまでを意味する。
LINE承認の競合試験（T09、T13、T14、T15）に合格したことではない。
接続先は localhost に限る。サイト用DBを使う場合も、この試験が作った行だけを消す。
"""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError


def test_migration_creates_registration_constraints(conflict_engine):
    with conflict_engine.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
        }
        assert {
            "line_registration_sessions",
            "line_registration_contexts",
            "line_registration_submit_keys",
        } <= tables
        birth = connection.execute(
            text(
                """
                SELECT is_nullable
                FROM information_schema.columns
                WHERE table_name = 'worker_registration_request_details'
                  AND column_name = 'birth_date'
                """
            )
        ).scalar_one()
        assert birth == "YES"
        partial = connection.execute(
            text(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE indexname = 'uq_line_registration_contexts_open_subject'
                """
            )
        ).scalar_one()
        assert "UNIQUE" in partial.upper()
        assert "is_open" in partial


def _is_lock_timeout(exc: OperationalError) -> bool:
    origin = getattr(exc, "orig", None)
    sqlstate = getattr(origin, "sqlstate", None) or getattr(origin, "pgcode", None)
    if sqlstate == "55P03":
        return True
    message = f"{origin or ''} {exc}".lower()
    return "lock timeout" in message


HARNESS_SESSION_ID = "01HARNESSSESSION0000000000"


def _delete_harness_session(connection) -> None:
    connection.execute(
        text("DELETE FROM line_registration_sessions WHERE id = :id"),
        {"id": HARNESS_SESSION_ID},
    )


def test_second_connection_is_blocked_by_row_lock(conflict_engine):
    """基盤の準備確認。LINE承認の取引が競合に勝つことまでは見ない。"""
    with conflict_engine.begin() as connection:
        _delete_harness_session(connection)
        connection.execute(
            text(
                """
                INSERT INTO line_registration_sessions
                    (id, token_hash, line_user_id, expires_at, created_at, updated_at)
                VALUES
                    (:id, repeat('a', 64), 'subject-harness', now(), now(), now())
                """
            ),
            {"id": HARNESS_SESSION_ID},
        )

    first = conflict_engine.connect()
    second = conflict_engine.connect()
    first_tx = first.begin()
    try:
        first.execute(
            text(
                """
                SELECT id FROM line_registration_sessions
                WHERE id = :id
                FOR UPDATE
                """
            ),
            {"id": HARNESS_SESSION_ID},
        )
        second_tx = second.begin()
        try:
            second.execute(text("SET LOCAL lock_timeout = '300ms'"))
            with pytest.raises(OperationalError) as caught:
                second.execute(
                    text(
                        """
                        SELECT id FROM line_registration_sessions
                        WHERE id = :id
                        FOR UPDATE
                        """
                    ),
                    {"id": HARNESS_SESSION_ID},
                )
            assert _is_lock_timeout(caught.value)
        finally:
            second_tx.rollback()
    finally:
        first_tx.rollback()
        first.close()

    try:
        with second.begin():
            acquired = second.execute(
                text(
                    """
                    SELECT id FROM line_registration_sessions
                    WHERE id = :id
                    FOR UPDATE
                    """
                ),
                {"id": HARNESS_SESSION_ID},
            ).scalar_one()
        assert acquired == HARNESS_SESSION_ID
    finally:
        second.close()
        with conflict_engine.begin() as connection:
            _delete_harness_session(connection)
