"""Cabinet Office CSV is the holiday source inside its coverage; manual edits and later years stay."""
from datetime import date

from src.models.holiday_calendar import HolidayCsvImport
from src.models.transaction import AuditLog
from src.services.holiday_calendar import calendar, import_cabinet_csv, import_status
from tests.test_api_order_requests import _auth
from tests.test_order_billing import admin_user  # noqa: F401


def _csv(*rows: str) -> bytes:
    body = "国民の祝日・休日月日,国民の祝日・休日名称\n" + "\n".join(rows) + "\n"
    return body.encode("cp932")


def test_csv_import_keeps_manual_edits_and_marks_only_later_years_as_candidates(api_client, db_session, admin_user):
    headers = _auth(admin_user.username)
    assert api_client.get("/api/order-requests/holiday-calendar/import", headers=headers).json()["imported"] is False
    first = import_cabinet_csv(db_session, actor=admin_user, raw=_csv(
        "2026/11/3,文化の日", "2026/11/23,勤労感謝の日", "2027/1/1,元日"), source_url="https://example.test/holidays.csv")
    db_session.commit()
    assert first["label"].endswith("2026年11月〜2027年1月分")
    assert first["label"].startswith("内閣府CSV取込：")
    listed = {row["day"]: row for row in calendar(db_session, date(2026, 11, 1), date(2026, 11, 30))}
    assert listed["2026-11-03"]["name"] == "文化の日" and listed["2026-11-03"]["revision"] == 1
    assert listed["2026-11-23"]["name"] == "勤労感謝の日"
    assert calendar(db_session, date(2026, 1, 1), date(2026, 1, 1)) == []
    change = api_client.put("/api/order-requests/holiday-calendar", headers=headers, json={
        "day": "2026-11-23", "is_holiday": True, "name": "特別祝日", "revision": 1})
    assert change.status_code == 200, change.text
    second = import_cabinet_csv(db_session, actor=admin_user, raw=_csv(
        "2026/11/23,感謝の日", "2027/1/1,元日", "2027/2/11,建国記念の日"), source_url="https://example.test/holidays.csv")
    db_session.commit()
    record = db_session.query(HolidayCsvImport).order_by(HolidayCsvImport.imported_at.desc(), HolidayCsvImport.id.desc()).first()
    assert record.added_days == [{"day": "2027-02-11", "name": "建国記念の日"}]
    assert record.removed_days == [{"day": "2026-11-03", "name": "文化の日"}]
    assert record.renamed_days == [{"day": "2026-11-23", "before": "勤労感謝の日", "after": "感謝の日"}]
    assert record.imported_count == 3 and record.actor_user_id == admin_user.id
    kept = {row["day"]: row for row in calendar(db_session, date(2026, 11, 1), date(2027, 2, 28))}
    assert "2026-11-03" not in kept
    assert kept["2026-11-23"]["name"] == "特別祝日" and kept["2026-11-23"]["source"] == "manual"
    assert kept["2027-02-11"]["name"] == "建国記念の日" and kept["2027-02-11"]["source"] == "cabinet_csv"
    later = calendar(db_session, date(2028, 1, 1), date(2028, 1, 1))[0]
    assert later["name"] == "元日" and later["revision"] == 0 and later["source"] == "library"
    refreshing = import_status(db_session, today=date(2026, 11, 16))
    assert refreshing["needs_refresh"] is True and "残り3か月" in refreshing["notice"]
    assert second["imported"] is True
    import_cabinet_csv(db_session, actor=admin_user, raw=_csv(
        "2026/1/1,元日", "2027/11/23,勤労感謝の日"), source_url="https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv")
    db_session.commit()
    assert import_status(db_session, today=date(2026, 11, 16))["needs_refresh"] is False
    assert db_session.query(AuditLog).filter_by(action="holiday_csv_imported", actor=admin_user.username).count() == 3
