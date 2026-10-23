"""現場報告が本人・月に結び付き、金額と締め済み資料を変えないこと。DEC-090。"""
from datetime import timedelta, date
from decimal import Decimal
import importlib.util

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations

from src.api.jwt_auth import create_user_with_hashed_password
from src.models.attendance_note import AttendanceNote
from src.models.base import generate_ulid
from src.models.line_daily import WorkerScheduleEntry
from src.models.transaction import AuditLog, Payout, Closing
from src.services import worker_schedule as ws
from tests.test_api_line_order_requests import _auth, fake_line, line_env, ops_user, pdf_root  # noqa: F401
from tests.test_line_daily import _accepted_today


@pytest.fixture
def accepted(api_client, db_session, ops_user, pdf_root, line_env, fake_line):
    worker, version = _accepted_today(api_client, db_session, ops_user)
    entries = db_session.query(WorkerScheduleEntry).filter(WorkerScheduleEntry.worker_id == worker.id).order_by(WorkerScheduleEntry.work_date).all()
    return worker, entries, _auth(ops_user.username)


def _body(entry, **changes):
    return dict(schedule_entry_id=entry.id, kind="late", cause="personal", late_minutes=120,
                reason="現場責任者から2時間遅刻の報告", reported_by="現場ディレクター") | changes


def _period(entry):
    return entry.work_date.strftime("%Y%m")


def test_record_select_schedule_and_payment_summary_without_changing_money(api_client, db_session, accepted):
    worker, entries, auth = accepted
    entry = entries[0]
    original_status = entry.status
    payout = Payout(worker_id=worker.id, period_key=_period(entry), payment_date=entry.work_date,
                    status="closed", total_amount=Decimal("18000"), version=2, pdf_object_key="fixed.pdf")
    closing = Closing(period_key=_period(entry), status="hard_closed")
    db_session.add_all([payout, closing])
    db_session.commit()
    saved = api_client.post("/api/attendance-notes", json=_body(entry), headers=auth)
    assert saved.status_code == 201, saved.text
    note = saved.json()
    assert note["worker_id"] == worker.id and note["summary"] == "2時間遅刻"
    assert note["reported_by"] == "現場ディレクター" and note["actor_name"]
    params = {"period_key": _period(entry)}
    assert api_client.get("/api/attendance-notes/events", params=params, headers=auth).json()["items"][0]["series_id"] == entry.series_id
    choices = api_client.get("/api/attendance-notes/schedules", params={"series_id": entry.series_id, "day": str(entry.work_date)}, headers=auth).json()["items"]
    assert [c["worker_id"] for c in choices] == [worker.id]
    summary = api_client.get("/api/attendance-notes/payment-summary", params=params, headers=auth).json()
    assert summary["payouts"][payout.id] == {"worker_id": worker.id, "count": 1}
    db_session.expire_all()
    assert payout.total_amount == Decimal("18000") and payout.pdf_object_key == "fixed.pdf" and payout.status == "closed" and payout.version == 2
    assert closing.status == "hard_closed" and entry.status == original_status
    assert db_session.query(AuditLog).filter_by(action="attendance_note_recorded").count() == 1


def test_month_worker_test_and_void_filters_keep_history(api_client, db_session, accepted):
    worker, entries, auth = accepted
    e = entries[0]
    payload = api_client.post("/api/attendance-notes", json=_body(e, kind="cancel", late_minutes=None, cause="weather", reason="台風で全体中止"), headers=auth).json()
    assert "満額保証" in payload["payment_note"]
    params = {"period_key": _period(e), "worker_id": worker.id}
    assert api_client.get("/api/attendance-notes", params=params, headers=auth).json()["total"] == 1
    assert api_client.get("/api/attendance-notes", params=params | {"worker_id": "another"}, headers=auth).json()["total"] == 0
    other_month = (e.work_date.replace(day=1) - timedelta(days=1)).strftime("%Y%m")
    assert api_client.get("/api/attendance-notes", params=params | {"period_key": other_month}, headers=auth).json()["total"] == 0
    assert api_client.post(f"/api/attendance-notes/{payload['id']}/void", json={"reason": " "}, headers=auth).status_code == 422
    assert api_client.post(f"/api/attendance-notes/{payload['id']}/void", json={"reason": "報告対象日を訂正"}, headers=auth).status_code == 200
    assert api_client.get("/api/attendance-notes", params=params, headers=auth).json()["total"] == 0
    history = api_client.get("/api/attendance-notes", params=params | {"include_voided": True}, headers=auth).json()
    assert history["total"] == 1 and history["items"][0]["void_reason"] == "報告対象日を訂正"
    assert api_client.get("/api/attendance-notes/payment-summary", params=params, headers=auth).json()["total"] == 0
    assert db_session.query(AttendanceNote).count() == 1
    assert db_session.query(AuditLog).filter_by(action="attendance_note_voided").count() == 1
    # 訂正は元の履歴を保持したまま再登録できる。
    again = api_client.post("/api/attendance-notes", json=_body(e, kind="cancel", late_minutes=None), headers=auth)
    assert again.status_code == 201 and "支払対象外" in again.json()["payment_note"]


def test_duplicate_report_even_after_schedule_revision_is_rejected(api_client, db_session, accepted):
    worker, entries, auth = accepted
    e = entries[0]
    assert api_client.post("/api/attendance-notes", json=_body(e), headers=auth).status_code == 201
    assert api_client.post("/api/attendance-notes", json=_body(e), headers=auth).status_code == 409
    # 元の予定IDが変わっても、同一系列・本人・日・種別の二重登録はできない。
    duplicate = AttendanceNote(schedule_entry_id=entries[1].id, worker_id=worker.id, series_id=e.series_id,
        work_date=e.work_date, project_name=e.project_name, worker_name=worker.name, is_test=False,
        kind="late", cause="personal", late_minutes=60, reason="重複", reported_by="現場",
        actor_user_id=db_session.query(AttendanceNote).first().actor_user_id, actor_name="運営")
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_input_validation_and_permissions(api_client, db_session, accepted):
    _, entries, auth = accepted
    e = entries[0]
    for changes in ({"reason": " "}, {"reported_by": " "}, {"late_minutes": None}, {"late_minutes": 1.5}, {"late_minutes": True}, {"kind": "cancel"}, {"cause": "unknown"}):
        assert api_client.post("/api/attendance-notes", json=_body(e, **changes), headers=auth).status_code == 422
    assert api_client.post("/api/attendance-notes", json=_body(e, schedule_entry_id="missing"), headers=auth).status_code == 404
    for month in ("202613", "000000", "2026-10"):
        assert api_client.get("/api/attendance-notes", params={"period_key": month}, headers=auth).status_code == 422
    for role in ("accounting", "site_manager", "worker"):
        create_user_with_hashed_password(db_session, f"note_{role}", f"note_{role}@example.com", "pass123", role)
    db_session.commit()
    params = {"period_key": _period(e)}
    for role in ("accounting", "site_manager", "worker"):
        headers = _auth(f"note_{role}")
        assert api_client.post("/api/attendance-notes", json=_body(e), headers=headers).status_code == 403
        assert api_client.get("/api/attendance-notes", params=params, headers=headers).status_code == (200 if role == "accounting" else 403)
    assert api_client.get("/api/attendance-notes", params=params).status_code == 401


def test_cancelled_schedule_is_still_recordable_and_test_never_enters_payment(api_client, db_session, accepted):
    _, entries, auth = accepted
    e = entries[0]
    e.status = "cancelled"
    e.is_test = True
    db_session.commit()
    response = api_client.post("/api/attendance-notes", json=_body(e, kind="cancel", late_minutes=None), headers=auth)
    assert response.status_code == 201
    params = {"period_key": _period(e)}
    assert api_client.get("/api/attendance-notes", params=params, headers=auth).json()["total"] == 0
    assert api_client.get("/api/attendance-notes", params=params | {"is_test": True}, headers=auth).json()["total"] == 1
    assert api_client.get("/api/attendance-notes/payment-summary", params=params, headers=auth).json()["total"] == 0


def test_database_rejects_null_late_minutes(api_client, db_session, accepted):
    _, entries, auth = accepted
    saved = api_client.post("/api/attendance-notes", json=_body(entries[0]), headers=auth).json()
    row = db_session.get(AttendanceNote, saved["id"])
    row.late_minutes = None
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_migration_refuses_to_drop_records(monkeypatch):
    spec = importlib.util.spec_from_file_location("attendance_migration", "alembic/versions/20261024a001_attendance_notes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Bind:
        def execute(self, _): return self
        def first(self): return (1,)
    monkeypatch.setattr(module.op, "get_bind", lambda: Bind())
    with pytest.raises(RuntimeError, match="削除できません"):
        module.downgrade()


def test_migration_creates_constraints_and_can_remove_empty_table(engine, monkeypatch):
    AttendanceNote.__table__.drop(engine)
    spec = importlib.util.spec_from_file_location("attendance_migration_ddl", "alembic/versions/20261024a001_attendance_notes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with engine.begin() as connection:
        monkeypatch.setattr(module, "op", Operations(MigrationContext.configure(connection)))
        module.upgrade()
        indexes = {i["name"]: i for i in inspect(connection).get_indexes("attendance_notes")}
        assert indexes["uq_attendance_notes_active"]["unique"]
        assert indexes["uq_attendance_notes_active"]["column_names"] == ["series_id", "worker_id", "work_date", "kind"]
        assert len(inspect(connection).get_check_constraints("attendance_notes")) == 5
        module.downgrade()
    # fixture teardown と整合するよう、空の表だけを復元する。
    AttendanceNote.__table__.create(engine)
