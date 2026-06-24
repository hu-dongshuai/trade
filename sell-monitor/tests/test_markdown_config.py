from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sell_monitor.storage.markdown_config import parse_env_text, read_json_payload, write_json_payload


class MarkdownConfigTest(unittest.TestCase):
    def test_reads_json_from_markdown_code_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "watchlist.md"
            path.write_text("# Watchlist\n\n```json\n{\n  \"symbols\": [\"002241\"]\n}\n```\n", encoding="utf-8")

            payload = read_json_payload(path)

            self.assertEqual(["002241"], payload["symbols"])

    def test_writes_json_as_markdown_code_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "positions.md"

            write_json_payload(path, {"positions": []}, title="Positions")

            content = path.read_text(encoding="utf-8")
            self.assertIn("# Positions", content)
            self.assertIn("```json", content)

    def test_reads_env_from_markdown_code_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sell-monitor-config.md"
            path.write_text("# Config\n\n```dotenv\nSELL_MONITOR_PROVIDER=akshare\n```\n", encoding="utf-8")

            content = parse_env_text(path)

            self.assertIn("SELL_MONITOR_PROVIDER=akshare", content)
