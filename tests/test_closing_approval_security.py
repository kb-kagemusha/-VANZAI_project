from datetime import datetime, timedelta, timezone
import pytest
from src.api.jwt_auth import create_user_with_hashed_password, create_access_token
from src.models.closing_approval import ClosingApprovalRequest
from src.models.transaction import Closing


def auth(user):
    return {"Authorization": "Bearer " + create_access_token({"sub": user.username})}


def request(client, db, project):
    first = create_user_with_hashed_password(db,"request-admin","request@example.com","test-only","admin")
    second = create_user_with_hashed_password(db,"approve-admin","approve@example.com","test-only","admin")
    worker = create_user_with_hashed_password(db,"no-approval","worker@example.com","test-only","worker")
    db.commit()
    assert client.post("/api/closing/soft",json={"project_id":project.id,"period_key":"202610"},headers=auth(first)).status_code == 200
    response = client.post("/api/closing/soft/release",json={"project_id":project.id,"period_key":"202610","approver":"invented-name","reason":"review"},headers=auth(first))
    assert response.status_code == 202
    return first, second, worker, response.json()["id"]


def test_name_only_request_does_not_release_and_self_or_worker_cannot_approve(api_client, db_session, project):
    first, second, worker, request_id = request(api_client,db_session,project)
    assert db_session.query(Closing).one().status == "soft_closed"
    assert api_client.post(f"/api/closing/approvals/{request_id}/approve",headers=auth(first)).status_code == 409
    assert api_client.post(f"/api/closing/approvals/{request_id}/approve",headers=auth(worker)).status_code == 403
    assert db_session.query(Closing).one().status == "soft_closed"
    assert api_client.post(f"/api/closing/approvals/{request_id}/approve",headers=auth(second)).status_code == 200
    assert api_client.post(f"/api/closing/approvals/{request_id}/approve",headers=auth(second)).status_code == 409
    assert db_session.query(Closing).one().release_count == 1


@pytest.mark.parametrize("invalid", ["expired", "inactive_requester", "changed_state"])
def test_invalid_approval_does_not_change_closing(api_client, db_session, project, invalid):
    first, second, worker, request_id = request(api_client,db_session,project)
    row = db_session.get(ClosingApprovalRequest,request_id)
    if invalid == "expired": row.expires_at = datetime.now(timezone.utc)-timedelta(seconds=1)
    elif invalid == "inactive_requester": first.is_active = False
    else: db_session.query(Closing).one().release_count = 1
    db_session.commit()
    assert api_client.post(f"/api/closing/approvals/{request_id}/approve",headers=auth(second)).status_code == 409
    assert db_session.query(Closing).one().status == "soft_closed"
    assert db_session.get(ClosingApprovalRequest,request_id).status == "pending"
