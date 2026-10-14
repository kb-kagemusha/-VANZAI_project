"""通常の稼働者更新は、7項目の比較票がないと書き戻さない。"""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from src.api.jwt_auth import create_user_with_hashed_password
from src.domain.worker_edit_guard import _b64, _secret, issue_worker_edit_guard
from src.models.enums import UserRole


def _auth_header(username: str) -> dict[str, str]:
    from src.api.jwt_auth import create_access_token

    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


def _admin(db_session, username: str):
    user = create_user_with_hashed_password(
        db=db_session,
        username=username,
        email=f"{username}@example.com",
        password="secret123",
        role=UserRole.ADMIN.value,
    )
    db_session.commit()
    return user


def test_create_worker_does_not_require_edit_guard(api_client, db_session):
    user = _admin(db_session, "admin_create_without_guard")
    created = api_client.post(
        "/api/workers",
        json={"name": "新規稼働者", "is_active": True},
        headers=_auth_header(user.username),
    )
    assert created.status_code == 200
    assert created.json()["name"] == "新規稼働者"


def test_update_without_guard_is_conflict(api_client, db_session, worker):
    user = _admin(db_session, "admin_missing_guard")
    response = api_client.put(
        f"/api/workers/{worker.id}",
        json={"name": "書き戻し", "is_active": True},
        headers=_auth_header(user.username),
    )
    assert response.status_code == 409
    db_session.expire_all()
    assert db_session.get(type(worker), worker.id).name == worker.name


def test_update_with_current_guard_succeeds(api_client, db_session, worker):
    user = _admin(db_session, "admin_current_guard")
    headers = _auth_header(user.username)
    guard = api_client.get(f"/api/workers/{worker.id}/edit-guard", headers=headers)
    assert guard.status_code == 200
    assert guard.json()["worker"]["id"] == worker.id
    response = api_client.put(
        f"/api/workers/{worker.id}",
        json={"name": "比較後の氏名", "is_active": True, "edit_guard": guard.json()["edit_guard"]},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "比較後の氏名"


def test_stale_guard_does_not_overwrite(api_client, db_session, worker):
    user = _admin(db_session, "admin_stale_guard")
    headers = _auth_header(user.username)
    guard = api_client.get(f"/api/workers/{worker.id}/edit-guard", headers=headers)
    ticket = guard.json()["edit_guard"]
    worker.phone = "09011112222"
    db_session.commit()
    response = api_client.put(
        f"/api/workers/{worker.id}",
        json={"name": "古い画面の氏名", "phone": "08000000000", "is_active": True, "edit_guard": ticket},
        headers=headers,
    )
    assert response.status_code == 409
    db_session.expire_all()
    saved = db_session.get(type(worker), worker.id)
    assert saved.name == worker.name
    assert saved.phone == "09011112222"


def test_expired_or_wrong_purpose_guard_is_rejected(api_client, db_session, worker):
    user = _admin(db_session, "admin_bad_guard")
    headers = _auth_header(user.username)
    expired = issue_worker_edit_guard(
        worker,
        user.id,
        now=datetime.now(timezone.utc) - timedelta(minutes=61),
    )
    expired_response = api_client.put(
        f"/api/workers/{worker.id}",
        json={"name": "期限切れ", "is_active": True, "edit_guard": expired},
        headers=headers,
    )
    assert expired_response.status_code == 409

    tampered = issue_worker_edit_guard(worker, user.id) + "x"
    tampered_response = api_client.put(
        f"/api/workers/{worker.id}",
        json={"name": "改ざん", "is_active": True, "edit_guard": tampered},
        headers=headers,
    )
    assert tampered_response.status_code == 409

    other = _admin(db_session, "admin_other_guard")
    foreign = issue_worker_edit_guard(worker, other.id)
    foreign_response = api_client.put(
        f"/api/workers/{worker.id}",
        json={"name": "他人の票", "is_active": True, "edit_guard": foreign},
        headers=headers,
    )
    assert foreign_response.status_code == 409

    wrong_purpose = _retarget_purpose(issue_worker_edit_guard(worker, user.id), "line_approval")
    purpose_response = api_client.put(
        f"/api/workers/{worker.id}",
        json={"name": "別用途", "is_active": True, "edit_guard": wrong_purpose},
        headers=headers,
    )
    assert purpose_response.status_code == 409

    for malformed in ("比較票.abc", "abc.比較票", "あいう"):
        malformed_response = api_client.put(
            f"/api/workers/{worker.id}",
            json={"name": "形式不正", "is_active": True, "edit_guard": malformed},
            headers=headers,
        )
        assert malformed_response.status_code == 409
    db_session.expire_all()
    assert db_session.get(type(worker), worker.id).name == worker.name


def test_edit_guard_after_other_admin_matches_latest_phone(api_client, db_session, worker):
    """保存後に取り直した比較票と表示値は、別管理者の変更後の電話に揃う。"""
    first = _admin(db_session, "admin_save_first")
    second = _admin(db_session, "admin_change_phone")
    first_headers = _auth_header(first.username)
    second_headers = _auth_header(second.username)

    opened = api_client.get(f"/api/workers/{worker.id}/edit-guard", headers=first_headers)
    assert opened.status_code == 200
    saved = api_client.put(
        f"/api/workers/{worker.id}",
        json={"name": "自分の保存", "phone": "08000000000", "is_active": True, "edit_guard": opened.json()["edit_guard"]},
        headers=first_headers,
    )
    assert saved.status_code == 200

    other = api_client.get(f"/api/workers/{worker.id}/edit-guard", headers=second_headers)
    changed = api_client.put(
        f"/api/workers/{worker.id}",
        json={"name": "自分の保存", "phone": "09011112222", "is_active": True, "edit_guard": other.json()["edit_guard"]},
        headers=second_headers,
    )
    assert changed.status_code == 200

    refreshed = api_client.get(f"/api/workers/{worker.id}/edit-guard", headers=first_headers)
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["worker"]["phone"] == "09011112222"
    assert body["edit_guard"]

    kept = api_client.put(
        f"/api/workers/{worker.id}",
        json={
            "name": body["worker"]["name"],
            "phone": body["worker"]["phone"],
            "email": body["worker"]["email"],
            "is_active": body["worker"]["is_active"],
            "edit_guard": body["edit_guard"],
        },
        headers=first_headers,
    )
    assert kept.status_code == 200
    db_session.expire_all()
    assert db_session.get(type(worker), worker.id).phone == "09011112222"


def _retarget_purpose(token: str, purpose: str) -> str:
    import base64

    encoded, _signature = token.split(".", 1)
    padding = "=" * (-len(encoded) % 4)
    body = json.loads(base64.urlsafe_b64decode(encoded + padding))
    body["purpose"] = purpose
    retargeted = _b64(json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(_secret(), retargeted.encode("ascii"), hashlib.sha256).digest()
    return f"{retargeted}.{_b64(signature)}"
