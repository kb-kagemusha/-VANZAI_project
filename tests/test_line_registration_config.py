"""Startup settings must not read secret files or apply invalid values."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.domain.line_registration_config import load_line_registration_config
from src.domain.line_registration_entry import registration_entry_ready


class RegistrationConfigTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "line-registration-config.json"
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def write(self, **changes):
        settings = {
            "LINE_LOGIN_CHANNEL_ID": "1234567890",
            "LINE_LIFF_ID": "1234567890-Test123",
            "LINE_WORKER_REGISTRATION_ENABLED": True,
        }
        settings.update(changes)
        self.path.write_text(json.dumps(settings), encoding="utf-8")

    def test_missing_preserves_existing_environment(self):
        os.environ["LINE_LOGIN_CHANNEL_ID"] = "existing"
        self.assertFalse(load_line_registration_config(self.path))
        self.assertEqual(os.environ["LINE_LOGIN_CHANNEL_ID"], "existing")

    def test_valid_settings_enable_entry_without_touching_secrets(self):
        os.environ["LINE_CHANNEL_SECRET"] = "unchanged"
        self.write()
        self.assertTrue(load_line_registration_config(self.path))
        self.assertTrue(registration_entry_ready())
        self.assertEqual(os.environ["LINE_CHANNEL_SECRET"], "unchanged")

    def test_explicit_false_disables_entry(self):
        self.write(LINE_WORKER_REGISTRATION_ENABLED=False)
        load_line_registration_config(self.path)
        self.assertFalse(registration_entry_ready())

    def test_invalid_settings_never_partly_apply(self):
        for changes in ({"LINE_LIFF_ID": "invalid"},
                        {"LINE_WORKER_REGISTRATION_ENABLED": "true"},
                        {"LINE_CHANNEL_SECRET": "must-not-load"}):
            with self.subTest(changes=tuple(changes)):
                self.write(**changes)
                before = dict(os.environ)
                with self.assertRaises(RuntimeError):
                    load_line_registration_config(self.path)
                self.assertEqual(dict(os.environ), before)

    def test_malformed_json_does_not_expose_content(self):
        self.path.write_text("private broken content", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "^Invalid LINE registration configuration$"):
            load_line_registration_config(self.path)


if __name__ == "__main__":
    unittest.main()
