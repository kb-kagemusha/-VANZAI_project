"""ログインセッションの継続（リフレッシュトークン）"""
from src.api.jwt_auth import create_user_with_hashed_password


def _login(api_client, username: str, password: str) -> dict:
    response = api_client.post(
        "/api/auth/token",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def test_refresh_token_issues_a_new_access_token(api_client, db_session):
    create_user_with_hashed_password(
        db=db_session,
        username="refresh_user",
        email="refresh_user@example.com",
        password="secret123",
        role="ops",
    )
    tokens = _login(api_client, "refresh_user", "secret123")

    refreshed = api_client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"

    me = api_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == "refresh_user"


def test_refresh_rejects_access_token(api_client, db_session):
    create_user_with_hashed_password(
        db=db_session,
        username="refresh_reject_user",
        email="refresh_reject_user@example.com",
        password="secret123",
        role="ops",
    )
    tokens = _login(api_client, "refresh_reject_user", "secret123")

    refreshed = api_client.post("/api/auth/refresh", json={"refresh_token": tokens["access_token"]})

    assert refreshed.status_code == 401


def test_valid_access_token_can_issue_persistent_session(api_client, db_session):
    create_user_with_hashed_password(
        db=db_session,
        username="session_user",
        email="session_user@example.com",
        password="secret123",
        role="admin",
    )
    tokens = _login(api_client, "session_user", "secret123")

    session = api_client.post(
        "/api/auth/session",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert session.status_code == 200
    body = session.json()
    me = api_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == "session_user"
