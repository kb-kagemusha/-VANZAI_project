"""LINE登録のロック順。申請、稼働者、紐付けの順で取る。

送信、承認、解除、コード紐付けは同じ順にする。通常編集は稼働者だけを取る。
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def _postgresql(session: Session) -> bool:
    bind = session.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def lock_request_row(session: Session, request_id: str | None) -> None:
    if not request_id or not _postgresql(session):
        return
    session.execute(
        text("SELECT id FROM registration_requests WHERE id = :id FOR UPDATE"),
        {"id": request_id},
    )


def lock_worker_row(session: Session, worker_id: str | None) -> None:
    if not worker_id or not _postgresql(session):
        return
    session.execute(
        text("SELECT id FROM workers WHERE id = :id FOR UPDATE"),
        {"id": worker_id},
    )


def lock_link_rows(
    session: Session,
    *,
    line_user_id: str | None = None,
    worker_id: str | None = None,
) -> None:
    if not _postgresql(session):
        return
    if line_user_id and worker_id:
        session.execute(
            text(
                """
                SELECT id FROM line_worker_links
                WHERE line_user_id = :line_user_id OR worker_id = :worker_id
                FOR UPDATE
                """
            ),
            {"line_user_id": line_user_id, "worker_id": worker_id},
        )
        return
    if line_user_id:
        session.execute(
            text("SELECT id FROM line_worker_links WHERE line_user_id = :line_user_id FOR UPDATE"),
            {"line_user_id": line_user_id},
        )
        return
    if worker_id:
        session.execute(
            text("SELECT id FROM line_worker_links WHERE worker_id = :worker_id FOR UPDATE"),
            {"worker_id": worker_id},
        )
