import json
import pytest
from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.services import google_places


@pytest.fixture
def admin(db_session):
    user = create_user_with_hashed_password(db=db_session, username="places_admin", email="places@example.test", password="test-password", role="admin")
    db_session.commit()
    from src.api.place_routes import _searches
    _searches.clear()
    return {"Authorization": "Bearer " + create_access_token({"sub": user.username})}


def test_missing_settings_explicit_and_no_secret_returned(api_client, admin, monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    status = api_client.get("/api/places/status", headers=admin)
    assert status.json() == {"configured": False}
    assert status.headers["Cache-Control"] == "no-store"
    assert api_client.get("/api/places/search", params={"query": "会場名"}, headers=admin).status_code == 503


def test_official_provider_mask_language_and_no_persisted_content(api_client, admin, monkeypatch, db_session):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "dummy-places-key")
    calls = []
    class Result:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return json.dumps({"places": [{"id": "test-place", "displayName": {"text": "会場名"}, "formattedAddress": "横浜市の住所", "attributions": []}]}).encode()
    def request(req, timeout):
        calls.append(req)
        assert req.full_url == "https://places.googleapis.com/v1/places:searchText"
        assert req.get_header("X-goog-api-key") == "dummy-places-key"
        assert json.loads(req.data)["languageCode"] == "ja"
        return Result()
    monkeypatch.setattr(google_places.urllib.request, "urlopen", request)
    response = api_client.get("/api/places/search", params={"query": "会場名"}, headers=admin)
    assert response.status_code == 200
    assert response.json()["items"][0]["address"] == "横浜市の住所"
    assert "dummy-places-key" not in response.text
    assert response.headers["Cache-Control"] == "no-store"
    from src.models.order_request import OrderRequestVersion
    assert db_session.query(OrderRequestVersion).count() == 0


def test_provider_errors_do_not_expose_key_or_raw_response(api_client, admin, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "dummy-places-key")
    def failed(*args, **kwargs): raise google_places.urllib.error.URLError("dummy-places-key")
    monkeypatch.setattr(google_places.urllib.request, "urlopen", failed)
    result = api_client.get("/api/places/search", params={"query": "会場名"}, headers=admin)
    assert result.status_code == 502 and "dummy-places-key" not in result.text


def test_unauthenticated_search_and_short_input_rejected(api_client, admin):
    assert api_client.get("/api/places/search", params={"query": "会場名"}).status_code in (401, 403)
    assert api_client.get("/api/places/search", params={"query": "a"}, headers=admin).status_code == 422
