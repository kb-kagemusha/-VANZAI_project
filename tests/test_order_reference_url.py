import json

import pytest

from src.services.order_request_format import canonical_conditions, compose_document, parse_sections
from tests.test_api_order_requests import _auth, _worker, ops_user, pdf_root  # noqa: F401
from tests.test_line_daily import _payload


@pytest.mark.parametrize("url", ["", "https://example.com/~event?q=1&x=2", "http://example.com/event"])
def test_reference_url_is_optional_separate_and_not_normalized(url):
    sections = parse_sections(json.dumps({"format": "additional-request-v1", "project_name": "案内イベント", "reference_url": url}))
    assert json.loads(canonical_conditions(sections))["reference_url"] == url
    body = compose_document(sections, work_date_label="日程", site_name="会場")
    assert "■案件名\n案内イベント\n" in body
    assert ("■参考URL" in body) is bool(url)
    if url:
        assert f"■参考URL\n{url}" in body


@pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://example.com", "https://", "https://user:pass@example.com", "https://example.com/\nx", "https://example.com:bad", 123, "https://example.com/" + "a" * 4096])
def test_invalid_reference_url_is_rejected(url):
    with pytest.raises(ValueError, match="参考URL"):
        parse_sections(json.dumps({"format": "additional-request-v1", "reference_url": url}))


def test_reference_and_address_survive_template_and_do_not_replace_required_name(api_client, db_session, ops_user, pdf_root):
    auth = _auth(ops_user.username)
    payload = _payload([_worker(db_session, "URL確認用").id])
    sections = json.loads(payload["request_conditions"])
    sections.update(reference_url="https://example.com/~event", project_name="")
    payload.update(request_conditions=json.dumps(sections), site_address="〒231-0001 神奈川県横浜市中区新港1丁目1-1")
    response = api_client.post("/api/order-requests", headers=auth, json=payload)
    assert response.status_code == 200, response.text
    row = response.json()
    rejected = api_client.post(f"/api/order-requests/versions/{row['id']}/confirm", headers=auth)
    assert rejected.status_code == 400 and "案件名" in rejected.json()["detail"]
    sections["project_name"] = "案内イベント"
    updated = api_client.patch(f"/api/order-requests/versions/{row['id']}", headers=auth, json={"request_conditions": json.dumps(sections)})
    assert updated.status_code == 200, updated.text
    saved = api_client.post("/api/order-requests/templates", headers=auth, json={"name": "URL付き", "source_version_id": row["id"]})
    assert saved.status_code == 200, saved.text
    copied = api_client.get(f"/api/order-requests/templates/{saved.json()['id']}", headers=auth).json()["payload"]
    assert json.loads(copied["request_conditions"])["reference_url"] == sections["reference_url"]
    assert copied["site_address"] == payload["site_address"]
    assert "■参考URL\nhttps://example.com/~event" in copied["body"]
    assert payload["site_address"] in copied["body"]


def test_legacy_name_is_preserved_without_bulk_migration():
    name = "従来のイベント\nhttps://example.com/old"
    sections = parse_sections(json.dumps({"format": "additional-request-v1", "project_name": name}))
    assert json.loads(canonical_conditions(sections))["project_name"] == name
    assert "reference_url" not in sections
