"""Validate user-provided Google Maps share URLs; never resolve short links on the server."""
from urllib.parse import urlsplit


def validate_maps_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if len(value) > 4096 or any(char.isspace() for char in value) or "\\" in value:
        raise ValueError("Google Mapsの共有URLを入力してください")
    try:
        url = urlsplit(value)
        if url.scheme != "https" or url.username or url.password or url.port not in (None, 443):
            raise ValueError
        host = url.hostname
        allowed = (
            host in ("google.com", "www.google.com", "google.co.jp", "www.google.co.jp") and (url.path == "/maps" or url.path.startswith("/maps/"))
            or host in ("maps.google.com", "maps.google.co.jp")
            or host == "maps.app.goo.gl" and bool(url.path.strip("/"))
            or host == "goo.gl" and url.path.startswith("/maps/")
        )
        if not allowed:
            raise ValueError
    except ValueError:
        raise ValueError("Google Mapsの共有URLを入力してください（https://maps.app.goo.gl/… など）") from None
    return value
