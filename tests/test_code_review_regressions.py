"""Regressions for monthly aggregation, attendance and previously untested APIs."""
from datetime import date, time
from decimal import Decimal
import json
from typing import get_type_hints

import pytest
from sqlalchemy import event
from sqlalchemy.dialects import postgresql

from src.api.jwt_auth import create_access_token
from src.domain.period import month_date_range
from src.exceptions import RecordNotFoundException, ValidationException
from src.models.master import IncentiveRule, User
from src.models.transaction import Actual
from src.services.aggregation import aggregate_by_client, aggregate_by_project
from src.services.incentive_service import IncentiveCreateInput, IncentiveService
from src.services.recalculation import RecalculationService
from src.services import invoice_service, payout_service
from tests.test_recalculation import create_test_actual


@pytest.fixture
def active_actual(session, assignment, project, worker, role):
    return create_test_actual(session, assignment, project, worker, role, date(2026, 1, 15))


def auth(session, role, worker_id=None):
    user = User(username=f"review_{role}", email=f"{role}@example.com", role=role,
                worker_id=worker_id, is_active=True)
    session.add(user)
    session.commit()
    return {"Authorization": f"Bearer {create_access_token({'sub': user.username})}"}


@pytest.mark.parametrize("period", ["202601", "2026-01"])
def test_attendance_counts_active_days_once(session, active_actual, period):
    actual = active_actual
    rule = IncentiveRule(name="attendance", condition_type="attendance",
                         condition_json=json.dumps({"required_days": 2}),
                         incentive_amount=Decimal("1000"), valid_from=date(2026, 1, 1),
                         is_active=True)
    session.add(rule)
    # Two shifts on one day are one attendance day. Other statuses/months do not count.
    for day, status in [(15, "active"), (16, "invalid"), (17, "superseded")]:
        values = {c.name: getattr(actual, c.name) for c in Actual.__table__.columns
                  if c.name not in {"id", "created_at", "updated_at", "work_date", "status"}}
        session.add(Actual(**values, work_date=date(2026, 1, day), status=status))
    session.flush()
    service = IncentiveService(session)
    result = service.match_attendance_incentive(actual.worker_id, period, actual.project_id)
    assert not result.matched
    assert result.calculation_details["actual_days"] == 1
    rule.condition_json = json.dumps({"required_days": 1})
    result = service.match_attendance_incentive(actual.worker_id, period, actual.project_id)
    assert result.matched and result.amount == Decimal("1000")
    actual.assignment.status = "canceled"
    result = service.match_attendance_incentive(actual.worker_id, period, actual.project_id)
    assert not result.matched
    assert result.calculation_details["actual_days"] == 0


def test_aggregation_queries_are_portable_and_month_bounded(session, assignment, project):
    queries = []

    def capture(state):
        if state.is_select:
            queries.append(str(state.statement.compile(dialect=postgresql.dialect())))

    event.listen(session, "do_orm_execute", capture)
    try:
        assert len(aggregate_by_project(session, "202601")) == 1
        assert len(aggregate_by_client(session, "202601")) == 1
        assert aggregate_by_project(session, "202602") == []
        assert aggregate_by_client(session, "202602") == []
    finally:
        event.remove(session, "do_orm_execute", capture)
    assert queries
    assert all("strftime" not in query.lower() for query in queries)


@pytest.mark.parametrize("period,end", [("202402", date(2024, 2, 29)),
                                       ("2026-12", date(2026, 12, 31))])
def test_month_boundaries(period, end):
    start, actual_end = month_date_range(period)
    assert start.day == 1 and actual_end == end


@pytest.mark.parametrize("period", ["202613", "202600", "000001", "20261", "2026/01"])
def test_invalid_month_rejected(period):
    with pytest.raises(ValidationException):
        month_date_range(period)


def test_zero_billable_minutes_remain_zero_in_recalculation(session, active_actual):
    actual = active_actual
    actual.start_time, actual.end_time = time(9), time(10)
    actual.break_minutes_input = 60
    actual.calc_minutes_total, actual.calc_minutes_billable = 60, 0
    service = RecalculationService(session)
    preview = service.preview_recalculation(project_id=actual.project_id, period_key="202601")
    assert preview.current_total_sales == preview.current_total_outsource == 0
    assert preview.estimated_total_sales == preview.estimated_total_outsource == 0
    result = service.recalculate("review", project_id=actual.project_id, period_key="202601")
    assert result.recalculated_count == 1 and result.error_count == 0
    assert result.total_sales_before == result.total_sales_after == 0
    assert result.total_outsource_before == result.total_outsource_after == 0


@pytest.mark.parametrize("kind,status", [("invoice", "issued"), ("invoice", "closed"),
                                         ("payout", "approved"), ("payout", "paid"),
                                         ("payout", "closed")])
def test_fixed_actual_never_recalculated_even_with_force(session, active_actual, kind, status):
    actual = active_actual
    if kind == "invoice":
        document = invoice_service.generate_invoice(
            session, actual.assignment.shift_slot.project.client_id, actual.project_id,
            "202601", date(2026, 2, 1), "review")
    else:
        document = payout_service.generate_payout(
            session, actual.worker_id, actual.project_id, "202601", date(2026, 2, 1), "review")
    document.status = status
    session.flush()
    before = (actual.applied_price_sales, actual.applied_price_outsource,
              actual.calc_minutes_billable, document.total_amount)
    service = RecalculationService(session)
    preview = service.preview_recalculation(project_id=actual.project_id, period_key="202601")
    assert preview.target_count == 0 and preview.blocked_count == 1
    result = service.recalculate("review", project_id=actual.project_id,
                                 period_key="202601", force=True)
    assert result.recalculated_count == 0 and result.skipped_count == 1
    session.flush()
    assert before == (actual.applied_price_sales, actual.applied_price_outsource,
                      actual.calc_minutes_billable, document.total_amount)


def test_missing_incentive_rule_raises_domain_error(session):
    user = User(username="ops", email="ops@example.com", role="ops", is_active=True)
    with pytest.raises(RecordNotFoundException):
        IncentiveService(session).create_incentive(user, IncentiveCreateInput(
            incentive_rule_id="missing", worker_id="missing", project_id=None,
            period_key="202601", amount=Decimal("1000"), calculation_json="{}"))


def test_staff_master_linked_worker_crud(api_client, session, worker):
    headers = auth(session, "admin")
    body = {"name": "担当者", "linked_worker_id": worker.id}
    response = api_client.post("/api/vanzai-staff", json=body, headers=headers)
    assert response.status_code == 201, response.text
    staff_id = response.json()["id"]
    assert response.json()["linked_worker_name"] == worker.name
    response = api_client.put(f"/api/vanzai-staff/{staff_id}",
                              json={**body, "name": "更新担当者"}, headers=headers)
    assert response.status_code == 200, response.text
    response = api_client.get("/api/vanzai-staff", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["linked_worker_name"] == worker.name
    response = api_client.get("/api/vanzai-staff?offset=1&limit=1", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []
    assert response.json()["total"] == 1 and response.json()["offset"] == 1


def test_project_notice_visible_and_push_failure_does_not_fail_creation(
    api_client, session, assignment, project, worker, monkeypatch
):
    admin_headers = auth(session, "admin")
    worker_headers = auth(session, "worker", worker.id)

    def fail_push(*args, **kwargs):
        raise RuntimeError("simulated push failure")

    monkeypatch.setattr("src.services.push_sender.send_push_to_workers", fail_push)
    response = api_client.post("/api/notices", headers=admin_headers, json={
        "title": "案件通知", "body": "内容", "notice_type": "general",
        "priority": "normal", "target_type": "project", "target_project_id": project.id,
        "send_email": False,
    })
    assert response.status_code == 200, response.text
    response = api_client.get("/api/worker/notices", headers=worker_headers)
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["target_project_name"] == project.name


def test_confidence_return_annotation_can_be_resolved():
    from src.services.ocr.parsers.ocr_field_confidence import confidence_tone
    assert get_type_hints(confidence_tone)["return"] is not None
