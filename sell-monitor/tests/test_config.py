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
            explicit_env = root / ".env"
            os.environ["SELL_MONITOR_ENV_FILE"] = str(explicit_env)
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

    def test_loads_telegram_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "examples").mkdir()
            env_path = root / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "SELL_MONITOR_TELEGRAM_BOT_TOKEN=123456:abc",
                        "SELL_MONITOR_TELEGRAM_CHAT_ID=987654321",
                        "SELL_MONITOR_TELEGRAM_SUBJECT_PREFIX=[TG]",
                        "SELL_MONITOR_TELEGRAM_PROXY=http://127.0.0.1:7890",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            keys = [
                "SELL_MONITOR_ENV_FILE",
                "SELL_MONITOR_TELEGRAM_BOT_TOKEN",
                "SELL_MONITOR_TELEGRAM_CHAT_ID",
                "SELL_MONITOR_TELEGRAM_SUBJECT_PREFIX",
                "SELL_MONITOR_TELEGRAM_PROXY",
            ]
            previous = {key: os.environ.pop(key, None) for key in keys}
            try:
                os.environ["SELL_MONITOR_ENV_FILE"] = str(env_path)
                config = load_default_config(root)
                self.assertIsNotNone(config.telegram)
                assert config.telegram is not None
                self.assertEqual("123456:abc", config.telegram.bot_token)
                self.assertEqual("987654321", config.telegram.chat_id)
                self.assertEqual("[TG]", config.telegram.subject_prefix)
                self.assertEqual("http://127.0.0.1:7890", config.telegram.proxy_url)
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

    def test_loads_markdown_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_dir = root / "config"
            config_dir.mkdir(parents=True)
            (root / "examples").mkdir()
            env_md = config_dir / "sell-monitor-config.md"
            env_md.write_text(
                "# Config\n\n```dotenv\nSELL_MONITOR_PROVIDER=static\nSELL_MONITOR_SELL_WATCHLIST_PATH="
                + str(root / "config" / "sell-watchlist.md")
                + "\nSELL_MONITOR_ENTRY_WATCHLIST_PATH="
                + str(root / "config" / "entry-watchlist.md")
                + "\n```\n",
                encoding="utf-8",
            )
            old_env_file = os.environ.get("SELL_MONITOR_ENV_FILE")
            os.environ["SELL_MONITOR_ENV_FILE"] = str(env_md)
            old_provider = os.environ.pop("SELL_MONITOR_PROVIDER", None)
            old_watchlist = os.environ.pop("SELL_MONITOR_WATCHLIST_PATH", None)
            old_sell_watchlist = os.environ.pop("SELL_MONITOR_SELL_WATCHLIST_PATH", None)
            old_entry_watchlist = os.environ.pop("SELL_MONITOR_ENTRY_WATCHLIST_PATH", None)
            try:
                config = load_default_config(root)
                self.assertEqual("static", config.provider)
                self.assertEqual(root / "config" / "sell-watchlist.md", config.sell_watchlist_path)
                self.assertEqual(root / "config" / "entry-watchlist.md", config.entry_watchlist_path)
                self.assertEqual(root / "config" / "sell-watchlist.md", config.watchlist_path)
            finally:
                if old_env_file is None:
                    os.environ.pop("SELL_MONITOR_ENV_FILE", None)
                else:
                    os.environ["SELL_MONITOR_ENV_FILE"] = old_env_file
                if old_provider is not None:
                    os.environ["SELL_MONITOR_PROVIDER"] = old_provider
                else:
                    os.environ.pop("SELL_MONITOR_PROVIDER", None)
                if old_watchlist is not None:
                    os.environ["SELL_MONITOR_WATCHLIST_PATH"] = old_watchlist
                else:
                    os.environ.pop("SELL_MONITOR_WATCHLIST_PATH", None)
                if old_sell_watchlist is not None:
                    os.environ["SELL_MONITOR_SELL_WATCHLIST_PATH"] = old_sell_watchlist
                else:
                    os.environ.pop("SELL_MONITOR_SELL_WATCHLIST_PATH", None)
                if old_entry_watchlist is not None:
                    os.environ["SELL_MONITOR_ENTRY_WATCHLIST_PATH"] = old_entry_watchlist
                else:
                    os.environ.pop("SELL_MONITOR_ENTRY_WATCHLIST_PATH", None)
