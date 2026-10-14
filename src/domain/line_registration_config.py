"""Load optional, non-secret LINE registration settings at API startup."""
import json
import os
from pathlib import Path
import re


CONFIG_PATH = Path(__file__).resolve().parents[2] / "line-registration-config.json"
KEYS = {"LINE_LOGIN_CHANNEL_ID", "LINE_LIFF_ID", "LINE_WORKER_REGISTRATION_ENABLED"}


def load_line_registration_config(path: Path = CONFIG_PATH) -> bool:
    """Missing file preserves the environment; invalid settings never partly apply."""
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    try:
        settings = json.loads(content)
        if not isinstance(settings, dict) or set(settings) != KEYS:
            raise ValueError
        channel = settings["LINE_LOGIN_CHANNEL_ID"]
        liff = settings["LINE_LIFF_ID"]
        enabled = settings["LINE_WORKER_REGISTRATION_ENABLED"]
        if not isinstance(channel, str) or not re.fullmatch(r"[0-9]+", channel):
            raise ValueError
        if not isinstance(liff, str) or not re.fullmatch(r"[0-9]+-[A-Za-z0-9]+", liff):
            raise ValueError
        if type(enabled) is not bool:
            raise ValueError
        updates = {
            "LINE_LOGIN_CHANNEL_ID": channel,
            "LINE_LIFF_ID": liff,
            "LINE_WORKER_REGISTRATION_ENABLED": "true" if enabled else "false",
        }
    except (ValueError, TypeError):
        # Do not include file contents or values in startup logs.
        raise RuntimeError("Invalid LINE registration configuration") from None
    os.environ.update(updates)
    return True
