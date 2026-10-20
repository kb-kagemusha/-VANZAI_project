import json
import pytest
from src.domain.maps_url import validate_maps_url
from src.services.order_request_format import apply_template_fields, parse_sections


@pytest.mark.parametrize("url", ["https://maps.app.goo.gl/test", "https://www.google.com/maps/place/test/~data?query=~#anchor", "https://maps.google.com/?q=test", "https://www.google.co.jp/maps/search/?api=1&query=test", "https://goo.gl/maps/test"])
def test_maps_links_preserved_exactly_without_external_requests(url):
    assert validate_maps_url(url) == url
    raw = json.dumps({"format": "additional-request-v1", "maps_url": url})
    stored, body = apply_template_fields(raw, "", work_date_label="3/1", site_name="会場")
    assert parse_sections(stored)["maps_url"] == url
    assert url in body


@pytest.mark.parametrize("url", ["javascript:alert(1)", "http://maps.app.goo.gl/test", "https://www.google.com.evil.test/maps", "https://evil.test/maps", "https://www.google.com/search", "https://user:pass@www.google.com/maps", "https://maps.app.goo.gl:8080/test", "https://www.google.com\\@evil.test/maps", "https://maps.app.goo.gl/test bad"])
def test_non_maps_unsafe_links_rejected(url):
    with pytest.raises(ValueError): validate_maps_url(url)


def test_blank_link_removed_without_breaking_legacy_data():
    assert validate_maps_url("") == ""
    assert parse_sections('{"format":"additional-request-v1"}').get("maps_url") is None
