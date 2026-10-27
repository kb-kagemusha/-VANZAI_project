from datetime import datetime, time, timedelta, timezone
import pytest
from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.line_daily import WorkerScheduleEntry, WakeMonitorSend, WakeReport, WakeContactLog
from src.models.transaction import AuditLog
from src.services import worker_schedule as ws
from src.services.wake_monitor import WakeMonitorService
from src.services.wake_test_notifications import update, view
from tests.test_line_operator_portal import operator  # noqa: F401
from tests.test_line_daily import _accepted_today, ops_user, pdf_root, line_env, fake_line  # noqa: F401

PATH = "/api/line-daily/test-notification-settings"


@pytest.fixture
def admin(db_session):
    user = create_user_with_hashed_password(db=db_session, username="test-settings-admin", email="test-setting@example.com", password="test-password", role="admin")
    db_session.commit()
    return user


def headers(user):
    return {"Authorization": "Bearer " + create_access_token({"sub": user.username})}


def test_settings_default_admin_only_revision_and_audit(api_client, db_session, admin, operator):
    assert api_client.get(PATH).status_code == 401
    assert api_client.get(PATH, headers=headers(operator[1])).status_code == 403
    assert api_client.put(PATH, headers=headers(operator[1]), json={"enabled": False, "revision": 0}).status_code == 403
    auth = headers(admin)
    assert api_client.get(PATH, headers=auth).json()["enabled"] is False
    until = (ws.now_utc() + timedelta(hours=1)).isoformat()
    result = api_client.put(PATH, headers=auth, json={"enabled": True, "enabled_until": until, "revision": 0})
    assert result.status_code == 200, result.text
    assert result.json()["enabled"] is True and result.json()["revision"] == 1
    assert api_client.put(PATH, headers=auth, json={"enabled": False, "revision": 0}).status_code == 409
    result = api_client.put(PATH, headers=auth, json={"enabled": False, "revision": 1})
    assert result.status_code == 200 and result.json()["enabled"] is False
    assert result.json()["enabled_until"] is None and result.json()["updated_by"] == admin.username
    assert db_session.query(AuditLog).filter_by(action="wake_test_notifications_changed").count() == 2


@pytest.mark.parametrize("payload", [
    {"enabled": True}, {"enabled": True, "enabled_until": "2020-01-01T12:00:00+09:00"},
    {"enabled": True, "enabled_until": "2099-01-01T12:00:00+09:00"},
    {"enabled": True, "enabled_until": "2099-01-01T12:00:00"},
    {"enabled": False, "enabled_until": "2099-01-01T12:00:00+09:00"},
    {"enabled": "true"}, {"enabled": False, "unknown": 1},
])
def test_settings_reject_unbounded_or_invalid_windows(api_client, admin, payload):
    assert api_client.put(PATH, headers=headers(admin), json={"revision": 0, **payload}).status_code == 422
    assert api_client.get(PATH, headers=headers(admin)).json()["enabled"] is False


def setup_test_day(api_client, db_session, ops_user, monkeypatch):
    worker, _ = _accepted_today(api_client, db_session, ops_user)
    db_session.query(WorkerScheduleEntry).filter_by(worker_id=worker.id).update({"is_test": True})
    db_session.commit()
    day = ws.today_jst()
    def at(h, m):
        return datetime.combine(day, time(h, m), tzinfo=ws.JST).astimezone(timezone.utc)
    clock = [at(5, 50)]
    monkeypatch.setattr(ws, "now_utc", lambda: clock[0])
    return worker, day, at, clock


def test_test_notifications_only_during_window_then_off_with_old_buttons(api_client, db_session, admin, operator, ops_user, pdf_root, line_env, fake_line, monkeypatch):
    worker, day, at, clock = setup_test_day(api_client, db_session, ops_user, monkeypatch)
    update(db_session, admin, enabled=True, enabled_until=at(6, 30), revision=0); db_session.commit()
    fake_line.pushes.clear()
    clock[0] = at(6, 0)
    assert WakeMonitorService(db_session, fake_line).run()["worker_reminder"] == 1; db_session.commit()
    clock[0] = at(6, 15)
    assert WakeMonitorService(db_session, fake_line).run()["operator_alert"] == 1; db_session.commit()
    assert "【テスト】" in str(fake_line.pushes[-1])
    assert all(row.is_test for row in db_session.query(WakeMonitorSend).all())
    assert WakeMonitorService(db_session, fake_line).run()["operator_alert"] == 0
    clock[0] = at(6, 30)
    assert view(db_session)["enabled"] is False
    assert WakeMonitorService(db_session, fake_line).run()["operator_alert"] == 0
    assert WakeMonitorService(db_session, fake_line)._share_claim(worker.id, day, "運営", "Uanother", worker.name) == []
    db_session.add(WakeReport(worker_id=worker.id, report_date=day, is_test=True, event_occurred_at=clock[0], received_at=clock[0], late_received=False, line_event_id="after-off", created_at=clock[0]))
    db_session.commit()
    fake_line.pushes.clear()
    assert WakeMonitorService(db_session, fake_line).run()["operator_reported"] == 0
    assert fake_line.pushes == []


def test_enabling_does_not_flush_overdue_tests(api_client, db_session, admin, operator, ops_user, pdf_root, line_env, fake_line, monkeypatch):
    _worker, _day, at, clock = setup_test_day(api_client, db_session, ops_user, monkeypatch)
    clock[0] = at(6, 20)
    update(db_session, admin, enabled=True, enabled_until=at(7, 20), revision=0); db_session.commit()
    fake_line.pushes.clear()
    assert WakeMonitorService(db_session, fake_line).run() == {"worker_reminder": 0, "operator_alert": 0, "operator_reported": 0}
    assert fake_line.pushes == []
    assert db_session.query(WakeMonitorSend).count() == 0


def test_test_history_and_report_cannot_suppress_formal_day(api_client, db_session, admin, operator, ops_user, pdf_root, line_env, fake_line, monkeypatch):
    worker, day, at, clock = setup_test_day(api_client, db_session, ops_user, monkeypatch)
    # Formal schedule added after a test run on the same worker day.
    db_session.query(WorkerScheduleEntry).filter_by(worker_id=worker.id).update({"is_test": False})
    original = db_session.query(WorkerScheduleEntry).filter_by(worker_id=worker.id).first()
    values = {column.name: getattr(original, column.name) for column in WorkerScheduleEntry.__table__.columns if column.name not in ("id", "created_at", "updated_at")}
    values.update(is_test=True, start_time=time(8, 0), work_group_id="mixed-test-group")
    db_session.add(WorkerScheduleEntry(**values))
    db_session.add(WakeReport(worker_id=worker.id, report_date=day, is_test=True, event_occurred_at=at(5, 45), received_at=at(5, 45), late_received=False, line_event_id="test-report", created_at=at(5, 45)))
    db_session.add(WakeContactLog(worker_id=worker.id, contact_date=day, is_test=True, result="confirmed_awake", actor_user_id=admin.id, actor_name=admin.username, created_at=at(5, 45)))
    db_session.add(WakeMonitorSend(worker_id=worker.id, work_date=day, kind="worker_reminder", round=0, recipient="U123", is_test=True, status="sent", created_at=at(5, 45)))
    update(db_session, admin, enabled=True, enabled_until=at(7, 20), revision=0); db_session.commit()
    clock[0] = at(6, 15)
    fake_line.pushes.clear()
    counts = WakeMonitorService(db_session, fake_line).run()
    assert counts == {"worker_reminder": 1, "operator_alert": 1, "operator_reported": 0}
    assert all("【テスト】" not in str(push) for push in fake_line.pushes)
    from src.services.wake_status import build_wake_status
    mixed = build_wake_status(db_session, day, include_test=True)["items"][0]
    assert mixed["first_start"] == "09:00" and mixed["wake_reported_at"] is None
    outcome, _messages, shares = WakeMonitorService(db_session, fake_line).handle_postback("Uoperator", f"wa_claim:{worker.id}:{day}:test")
    assert outcome == "wake_alert_rejected" and shares == []


def test_test_shared_push_is_rechecked_after_it_was_queued(db_session, admin, fake_line, monkeypatch):
    from src.services.line_order import LineOrderService
    update(db_session, admin, enabled=True, enabled_until=ws.now_utc() + timedelta(hours=1), revision=0); db_session.commit()
    service = LineOrderService(db_session, fake_line)
    service._outbox.append(("wake_test_push", "Uoperator", [{"type": "text", "text": "【テスト】連絡します"}]))
    update(db_session, admin, enabled=False, enabled_until=None, revision=1); db_session.commit()
    fake_line.pushes.clear()
    service._send_outbox()
    assert fake_line.pushes == []


def test_expiry_mid_run_blocks_remaining_test_sends(api_client, db_session, admin, operator, ops_user, pdf_root, line_env, fake_line, monkeypatch):
    _worker, _day, at, clock = setup_test_day(api_client, db_session, ops_user, monkeypatch)
    update(db_session, admin, enabled=True, enabled_until=at(6, 30), revision=0); db_session.commit()
    clock[0] = at(6, 15)
    original = fake_line.push_messages
    def send_then_expire(to, messages):
        result = original(to, messages)
        clock[0] = at(6, 30)
        return result
    monkeypatch.setattr(fake_line, "push_messages", send_then_expire)
    fake_line.pushes.clear()
    result = WakeMonitorService(db_session, fake_line).run()
    assert result == {"worker_reminder": 1, "operator_alert": 0, "operator_reported": 0}
    assert len(fake_line.pushes) == 1


def test_test_reports_use_separate_context_and_notify_once(api_client, db_session, admin, operator, ops_user, pdf_root, line_env, fake_line, monkeypatch):
    worker, day, at, clock = setup_test_day(api_client, db_session, ops_user, monkeypatch)
    db_session.add(WakeReport(worker_id=worker.id, report_date=day, is_test=False, event_occurred_at=at(5, 45), received_at=at(5, 45), late_received=False, line_event_id="formal-report", created_at=at(5, 45)))
    update(db_session, admin, enabled=True, enabled_until=at(6, 30), revision=0); db_session.commit()
    clock[0] = at(6, 15)
    fake_line.pushes.clear()
    assert WakeMonitorService(db_session, fake_line).run()["operator_alert"] == 1; db_session.commit()
    clock[0] = at(6, 20)
    db_session.add(WakeReport(worker_id=worker.id, report_date=day, is_test=True, event_occurred_at=clock[0], received_at=clock[0], late_received=False, line_event_id="test-report-arrived", created_at=clock[0]))
    db_session.commit()
    fake_line.pushes.clear()
    assert WakeMonitorService(db_session, fake_line).run()["operator_reported"] == 1; db_session.commit()
    assert "【テスト】" in str(fake_line.pushes)
    assert WakeMonitorService(db_session, fake_line).run()["operator_reported"] == 0


def test_readonly_status_never_creates_a_line_client_or_sends(db_session, monkeypatch, capsys):
    import json
    from scripts.line import wake_monitor
    class ReadSession:
        def query(self, *args): return db_session.query(*args)
        def close(self): pass
    monkeypatch.setattr(wake_monitor, "SessionLocal", ReadSession)
    def reject(*args): raise AssertionError("Status must never start the monitor")
    monkeypatch.setattr(wake_monitor, "WakeMonitorService", reject)
    wake_monitor.main(["--status"])
    assert json.loads(capsys.readouterr().out)["enabled"] is False
