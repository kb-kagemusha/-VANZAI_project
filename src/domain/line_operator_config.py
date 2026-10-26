"""Non-secret operator LIFF configuration, separate from existing environment files."""
import json
import os
from pathlib import Path
import re
from src.domain.line_registration_entry import registration_login_channel_id

CONFIG_PATH = Path(__file__).resolve().parents[2] / "line-operator-config.json"


def load_line_operator_config(path=CONFIG_PATH):
    if not path.exists():
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if set(value) != {"enabled", "liff_id"} or type(value["enabled"]) is not bool:
            raise ValueError
        if not isinstance(value["liff_id"], str) or not re.fullmatch(r"[0-9]+-[A-Za-z0-9]+", value["liff_id"]):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise RuntimeError("Invalid operator LINE configuration") from None
    os.environ["LINE_OPERATOR_REGISTRATION_ENABLED"] = "true" if value["enabled"] else "false"
    os.environ["LINE_OPERATOR_LIFF_ID"] = value["liff_id"]
    return True


def operator_entry():
    liff_id = os.getenv("LINE_OPERATOR_LIFF_ID", "").strip()
    enabled = os.getenv("LINE_OPERATOR_REGISTRATION_ENABLED", "").lower() == "true"
    return {"enabled": bool(enabled and liff_id and registration_login_channel_id()), "liff_id": liff_id or None}
