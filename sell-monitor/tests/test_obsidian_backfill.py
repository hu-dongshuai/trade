from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from sell_monitor.domain.enums import Action, Priority
from sell_monitor.domain.models import Decision
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

    def test_backfilled_decision_can_trigger_followup_callback(self) -> None:
        decision = Decision(
            symbol="002241",
            action=Action.EXIT_ALL,
            total_score=7,
            priority=Priority.IMMEDIATE,
            reasons=["测试回溯卖出信号"],
            next_step="清仓",
            cancel_condition="无",
            symbol_name="歌尔股份",
            current_price=23.07,
        )
        replay = SimpleNamespace(decision=decision, notices=[], zones=[], daily_bars=[])
        recorder = SimpleNamespace(monitor_dir=Path(tempfile.gettempdir()), write_run=Mock())
        callback = Mock()
        as_of_dt = datetime(2026, 6, 24, 10, 30)

        with patch("sell_monitor.monitor.obsidian_backfill._target_checkpoints", return_value=[as_of_dt]):
            with patch("sell_monitor.monitor.obsidian_backfill._missing_checkpoints", return_value=[as_of_dt]):
                with patch("sell_monitor.monitor.obsidian_backfill.build_replay_decision", return_value=replay):
                    from sell_monitor.monitor.obsidian_backfill import backfill_missing_obsidian_records

                    backfill_missing_obsidian_records(
                        provider=SimpleNamespace(consume_notices=lambda: []),
                        recorder=recorder,
                        symbols=["002241"],
                        symbol_names={"002241": "歌尔股份"},
                        positions={},
                        rules={},
                        current_time=datetime(2026, 6, 25, 14, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                        on_backfilled_decision=callback,
                    )

        callback.assert_called_once_with(as_of_dt, decision)
        recorder.write_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
