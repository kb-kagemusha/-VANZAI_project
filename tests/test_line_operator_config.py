import json
import os
import pytest
from src.domain.line_operator_config import load_line_operator_config, operator_entry


@pytest.fixture(autouse=True)
def isolated_operator_settings(monkeypatch):
    monkeypatch.setenv("LINE_OPERATOR_REGISTRATION_ENABLED", "false")
    monkeypatch.setenv("LINE_OPERATOR_LIFF_ID", "")


def test_missing_operator_config_preserves_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("LINE_OPERATOR_REGISTRATION_ENABLED", "false")
    assert not load_line_operator_config(tmp_path / "absent.json")
    assert not operator_entry()["enabled"]


def test_operator_config_changes_only_nonsecret_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("LINE_LOGIN_CHANNEL_ID", "1234567890")
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "unchanged-secret")
    path = tmp_path / "operator.json"
    path.write_text(json.dumps({"enabled": True, "liff_id": "1234567890-Operator"}), encoding="utf-8")
    assert load_line_operator_config(path)
    assert operator_entry()["enabled"]
    assert os.environ["LINE_CHANNEL_SECRET"] == "unchanged-secret"


@pytest.mark.parametrize("settings", [{"enabled": "true", "liff_id": "1234-Abc"}, {"enabled": True, "liff_id": "https://wrong.example"}, {"enabled": True, "liff_id": "1234-Abc", "secret": "forbidden"}, None, [1, 2]])
def test_invalid_operator_config_does_not_partly_apply(tmp_path, settings):
    path = tmp_path / "operator.json"
    path.write_text(json.dumps(settings), encoding="utf-8")
    before = dict(os.environ)
    with pytest.raises(RuntimeError, match="^Invalid operator LINE configuration$"):
        load_line_operator_config(path)
    assert dict(os.environ) == before
