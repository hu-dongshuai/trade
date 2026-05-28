from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from sell_monitor.config import load_default_config


class ConfigTest(unittest.TestCase):
    def test_loads_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "examples").mkdir()
            (root / ".env").write_text("SELL_MONITOR_PROVIDER=akshare\n", encoding="utf-8")
            old_provider = os.environ.pop("SELL_MONITOR_PROVIDER", None)
            try:
                config = load_default_config(root)
                self.assertEqual("akshare", config.provider)
            finally:
                if old_provider is not None:
                    os.environ["SELL_MONITOR_PROVIDER"] = old_provider
                else:
                    os.environ.pop("SELL_MONITOR_PROVIDER", None)

    def test_placeholder_smtp_config_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "examples").mkdir()
            (root / ".env").write_text(
                "\n".join(
                    [
                        "SELL_MONITOR_PROVIDER=akshare",
                        "SELL_MONITOR_SMTP_HOST=smtp.example.com",
                        "SELL_MONITOR_EMAIL_FROM=you@example.com",
                        "SELL_MONITOR_EMAIL_TO=you@example.com",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            keys = [
                "SELL_MONITOR_PROVIDER",
                "SELL_MONITOR_SMTP_HOST",
                "SELL_MONITOR_EMAIL_FROM",
                "SELL_MONITOR_EMAIL_TO",
            ]
            previous = {key: os.environ.pop(key, None) for key in keys}
            try:
                config = load_default_config(root)
                self.assertIsNone(config.email)
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

    def test_loads_obsidian_monitor_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            monitor_dir = root / "monitor"
            (root / "examples").mkdir()
            (root / ".env").write_text(
                f"SELL_MONITOR_OBSIDIAN_MONITOR_DIR={monitor_dir}\n",
                encoding="utf-8",
            )
            old_env_file = os.environ.get("SELL_MONITOR_ENV_FILE")
            old_monitor_dir = os.environ.pop("SELL_MONITOR_OBSIDIAN_MONITOR_DIR", None)
            old_enabled = os.environ.pop("SELL_MONITOR_OBSIDIAN_MONITOR_ENABLED", None)
            try:
                config = load_default_config(root)
                self.assertIsNotNone(config.obsidian_monitor)
                self.assertEqual(monitor_dir, config.obsidian_monitor.monitor_dir)
            finally:
                if old_env_file is not None:
                    os.environ["SELL_MONITOR_ENV_FILE"] = old_env_file
                if old_monitor_dir is not None:
                    os.environ["SELL_MONITOR_OBSIDIAN_MONITOR_DIR"] = old_monitor_dir
                else:
                    os.environ.pop("SELL_MONITOR_OBSIDIAN_MONITOR_DIR", None)
                if old_enabled is not None:
                    os.environ["SELL_MONITOR_OBSIDIAN_MONITOR_ENABLED"] = old_enabled
                else:
                    os.environ.pop("SELL_MONITOR_OBSIDIAN_MONITOR_ENABLED", None)
