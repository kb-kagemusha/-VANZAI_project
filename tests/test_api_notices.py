"""
スタッフ通知 API テスト
POST/GET /api/notices, DELETE /api/notices/{id}
GET /api/worker/notices, POST /api/worker/notices/{id}/read
"""
from datetime import datetime, timezone

import pytest

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import UserRole
from src.models.master import StaffNotice, StaffNoticeRead, Worker


def _token(username: str) -> str:
    return create_access_token({"sub": username})


def _auth(username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(username)}"}


@pytest.fixture
def ops_user(db_session):
    u = create_user_with_hashed_password(
        db=db_session,
        username="notices_ops",
        email="notices_ops@example.com",
        password="pass123",
        role=UserRole.OPS.value,
    )
    db_session.commit()
    return u


@pytest.fixture
def worker_user(db_session):
    w = Worker(id=generate_ulid(), name="通知テスト稼働者", email="notice_worker@example.com", is_active=True)
    db_session.add(w)
    db_session.flush()
    u = create_user_with_hashed_password(
        db=db_session,
        username="notices_worker",
        email="notices_worker@example.com",
        password="pass123",
        role=UserRole.WORKER.value,
    )
    u.worker_id = w.id
    db_session.commit()
    return u, w


# ===========================
# POST /api/notices
# ===========================

def test_create_notice_all_workers(api_client, db_session, ops_user):
    """全員対象の通知を作成できる"""
    resp = api_client.post(
        "/api/notices",
        json={
            "title": "テスト一般お知らせ",
            "body": "本文です",
            "notice_type": "general",
            "priority": "normal",
            "target_type": "all",
            "send_email": False,
        },
        headers=_auth(ops_user.username),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["title"] == "テスト一般お知らせ"
    assert data["target_type"] == "all"
    assert data["notice_type"] == "general"
    assert data["send_email"] is False
    assert data["sent_at"] is None


def test_create_notice_urgent_shift_confirm(api_client, db_session, ops_user):
    """緊急シフト確定通知を作成できる"""
    resp = api_client.post(
        "/api/notices",
        json={
            "title": "緊急シフト確定",
            "body": "7月第2週のシフトが確定しました。",
            "notice_type": "shift_confirm",
            "priority": "urgent",
            "target_type": "all",
            "send_email": False,
        },
        headers=_auth(ops_user.username),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["priority"] == "urgent"
    assert data["notice_type"] == "shift_confirm"


def test_create_notice_target_worker_requires_ids(api_client, db_session, ops_user):
    """target_type=worker のときに target_worker_ids がないと 422"""
    resp = api_client.post(
        "/api/notices",
        json={
            "title": "個別通知テスト",
            "body": "本文",
            "notice_type": "general",
            "priority": "normal",
            "target_type": "worker",
            "send_email": False,
        },
        headers=_auth(ops_user.username),
    )
    assert resp.status_code == 422


def test_create_notice_requires_permission(api_client, db_session, worker_user):
    """WORKER ロールは通知作成不可"""
    u, _ = worker_user
    resp = api_client.post(
        "/api/notices",
        json={
            "title": "権限なし",
            "body": "本文",
            "notice_type": "general",
            "priority": "normal",
            "target_type": "all",
            "send_email": False,
        },
        headers=_auth(u.username),
    )
    assert resp.status_code == 403


# ===========================
# GET /api/notices
# ===========================

def test_list_notices(api_client, db_session, ops_user):
    """通知一覧を取得できる"""
    # 通知を2件作成
    for title in ["通知A", "通知B"]:
        api_client.post(
            "/api/notices",
            json={"title": title, "body": "本文", "notice_type": "general", "priority": "normal", "target_type": "all", "send_email": False},
            headers=_auth(ops_user.username),
        )

    resp = api_client.get("/api/notices", headers=_auth(ops_user.username))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2


def test_list_notices_filter_by_type(api_client, db_session, ops_user):
    """通知種別でフィルタできる"""
    api_client.post(
        "/api/notices",
        json={"title": "シフト通知", "body": "本文", "notice_type": "shift_confirm", "priority": "normal", "target_type": "all", "send_email": False},
        headers=_auth(ops_user.username),
    )
    api_client.post(
        "/api/notices",
        json={"title": "一般お知らせ", "body": "本文", "notice_type": "general", "priority": "normal", "target_type": "all", "send_email": False},
        headers=_auth(ops_user.username),
    )

    resp = api_client.get("/api/notices", params={"notice_type": "shift_confirm"}, headers=_auth(ops_user.username))
    assert resp.status_code == 200
    data = resp.json()
    types = {item["notice_type"] for item in data["items"]}
    assert types == {"shift_confirm"}


# ===========================
# DELETE /api/notices/{id}
# ===========================

def test_delete_notice(api_client, db_session, ops_user):
    """通知を論理削除できる"""
    create_resp = api_client.post(
        "/api/notices",
        json={"title": "削除テスト", "body": "本文", "notice_type": "general", "priority": "normal", "target_type": "all", "send_email": False},
        headers=_auth(ops_user.username),
    )
    notice_id = create_resp.json()["id"]

    del_resp = api_client.delete(f"/api/notices/{notice_id}", headers=_auth(ops_user.username))
    assert del_resp.status_code == 204

    # 削除後は一覧に出ない（deleted_at != None）
    list_resp = api_client.get("/api/notices", headers=_auth(ops_user.username))
    ids = [item["id"] for item in list_resp.json()["items"]]
    assert notice_id not in ids


# ===========================
# GET /api/worker/notices
# ===========================

def test_worker_sees_all_target_notices(api_client, db_session, ops_user, worker_user):
    """target_type=all の通知はスタッフが閲覧できる"""
    api_client.post(
        "/api/notices",
        json={"title": "全員向け", "body": "内容", "notice_type": "general", "priority": "normal", "target_type": "all", "send_email": False},
        headers=_auth(ops_user.username),
    )

    u, _ = worker_user
    resp = api_client.get("/api/worker/notices", headers=_auth(u.username))
    assert resp.status_code == 200
    data = resp.json()
    titles = [item["title"] for item in data["items"]]
    assert "全員向け" in titles


def test_worker_sees_targeted_notice(api_client, db_session, ops_user, worker_user):
    """target_type=worker で自分のIDが含まれる通知を閲覧できる"""
    u, w = worker_user

    api_client.post(
        "/api/notices",
        json={
            "title": "個別指定通知",
            "body": "あなた宛てです",
            "notice_type": "general",
            "priority": "normal",
            "target_type": "worker",
            "target_worker_ids": [w.id],
            "send_email": False,
        },
        headers=_auth(ops_user.username),
    )

    resp = api_client.get("/api/worker/notices", headers=_auth(u.username))
    assert resp.status_code == 200
    titles = [item["title"] for item in resp.json()["items"]]
    assert "個別指定通知" in titles


def test_worker_unread_count(api_client, db_session, ops_user, worker_user):
    """未読件数が正しく返る"""
    api_client.post(
        "/api/notices",
        json={"title": "未読テスト", "body": "内容", "notice_type": "general", "priority": "normal", "target_type": "all", "send_email": False},
        headers=_auth(ops_user.username),
    )

    u, _ = worker_user
    resp = api_client.get("/api/worker/notices", headers=_auth(u.username))
    assert resp.status_code == 200
    data = resp.json()
    assert data["unread_count"] >= 1


# ===========================
# POST /api/worker/notices/{id}/read
# ===========================

def test_mark_notice_read(api_client, db_session, ops_user, worker_user):
    """通知を既読にできる"""
    create_resp = api_client.post(
        "/api/notices",
        json={"title": "既読テスト", "body": "内容", "notice_type": "general", "priority": "normal", "target_type": "all", "send_email": False},
        headers=_auth(ops_user.username),
    )
    notice_id = create_resp.json()["id"]

    u, _ = worker_user
    read_resp = api_client.post(f"/api/worker/notices/{notice_id}/read", headers=_auth(u.username))
    assert read_resp.status_code == 204

    # 一覧で is_read=True になっている
    list_resp = api_client.get("/api/worker/notices", headers=_auth(u.username))
    for item in list_resp.json()["items"]:
        if item["id"] == notice_id:
            assert item["is_read"] is True
            break


def test_mark_notice_read_idempotent(api_client, db_session, ops_user, worker_user):
    """二重に既読リクエストしても 204 が返る（冪等）"""
    create_resp = api_client.post(
        "/api/notices",
        json={"title": "冪等テスト", "body": "内容", "notice_type": "general", "priority": "normal", "target_type": "all", "send_email": False},
        headers=_auth(ops_user.username),
    )
    notice_id = create_resp.json()["id"]

    u, _ = worker_user
    assert api_client.post(f"/api/worker/notices/{notice_id}/read", headers=_auth(u.username)).status_code == 204
    assert api_client.post(f"/api/worker/notices/{notice_id}/read", headers=_auth(u.username)).status_code == 204
