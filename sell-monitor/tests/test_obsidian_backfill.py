from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sell_monitor.monitor.obsidian_backfill import _missing_checkpoints, _target_checkpoints


class ObsidianBackfillTest(unittest.TestCase):
    def test_target_checkpoints_include_previous_two_trading_days_and_exclude_current_hour(self) -> None:
        current = datetime(2026, 5, 29, 14, 5, tzinfo=ZoneInfo("Asia/Shanghai"))

        targets = _target_checkpoints(current)
        target_text = [target.strftime("%Y-%m-%d %H:%M") for target in targets]

        self.assertIn("2026-05-27 09:30", target_text)
        self.assertIn("2026-05-28 15:00", target_text)
        self.assertIn("2026-05-29 13:00", target_text)
        self.assertNotIn("2026-05-29 14:00", target_text)

    def test_missing_checkpoints_treat_existing_same_hour_as_covered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "002241.md"
            path.write_text(
                "# 002241 监控记录\n\n"
                "| 检测时间 | 股票代码 |\n"
                "| 2026-05-28 10:12:30 | 002241 |\n",
                encoding="utf-8",
            )
            targets = [
                datetime(2026, 5, 28, 10, 30),
                datetime(2026, 5, 28, 11, 30),
            ]

            missing = _missing_checkpoints(Path(tmp), "002241", targets, datetime(2026, 5, 29, 10, 0))

            self.assertEqual([datetime(2026, 5, 28, 11, 30)], missing)


if __name__ == "__main__":
    unittest.main()
