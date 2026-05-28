from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sell_monitor.config import ObsidianMonitorConfig
from sell_monitor.domain.enums import Action, Priority
from sell_monitor.domain.models import Decision
from sell_monitor.notifier.channels.obsidian import ObsidianMarkdownChannel, ObsidianMonitorRunRecorder


class ObsidianMarkdownChannelTest(unittest.TestCase):
    def test_prepends_latest_monitor_result_to_symbol_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            channel = ObsidianMarkdownChannel(ObsidianMonitorConfig(monitor_dir=Path(tmp)))

            channel.send("[SellMonitor] 002241 hold score=0", "[002241] first result")
            channel.send("[SellMonitor] 002241 exit_all score=999", "[002241] latest result")

            content = (Path(tmp) / "002241.md").read_text(encoding="utf-8")
            self.assertTrue(content.startswith("# 002241 监控记录"))
            self.assertLess(content.index("latest result"), content.index("first result"))

    def test_writes_each_symbol_to_separate_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            channel = ObsidianMarkdownChannel(ObsidianMonitorConfig(monitor_dir=Path(tmp)))

            channel.send("[SellMonitor] 002241 hold score=0", "[002241] result")
            channel.send("[SellMonitor] 002739 hold score=0", "[002739] result")

            self.assertTrue((Path(tmp) / "002241.md").exists())
            self.assertTrue((Path(tmp) / "002739.md").exists())

    def test_run_recorder_writes_no_signal_record_for_each_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))

            recorder.write_run(
                symbols=["002241", "002739"],
                decisions=[],
                notices=["[002241] 未接近日线 A/B 级关键价位，暂不启动 15 分钟监测"],
            )

            first = (Path(tmp) / "002241.md").read_text(encoding="utf-8")
            second = (Path(tmp) / "002739.md").read_text(encoding="utf-8")
            self.assertIn("| 检测时间 | 股票代码 | 结论 | 动作 | 分数 | 优先级 | 原因/提示 | 下一步 | 取消条件 |", first)
            self.assertIn("未触发卖出信号", first)
            self.assertIn("[002241] 未接近日线 A/B 级关键价位", first)
            self.assertIn("未触发卖出信号", second)
            self.assertNotIn("[002241] 未接近日线 A/B 级关键价位", second)

    def test_run_recorder_marks_sell_signal_time_in_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))
            decision = Decision(
                symbol="002241",
                action=Action.REDUCE,
                total_score=3,
                priority=Priority.HIGH,
                reasons=["15分钟关键价位放量危险上影线"],
                next_step="减仓 50%",
                cancel_condition="重新站回关键价位上方并缩量企稳",
            )

            recorder.write_run(symbols=["002241"], decisions=[decision], notices=[])

            content = (Path(tmp) / "002241.md").read_text(encoding="utf-8")
            self.assertIn('<span style="color:red">', content)
            self.assertIn("| <span style=\"color:red\">", content)
            self.assertIn("| 002241 | 卖出信号 | reduce | 3 | high |", content)

    def test_run_recorder_summarizes_sell_signals_to_daily_trigger_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))
            decision = Decision(
                symbol="002241",
                action=Action.EXIT_ALL,
                total_score=5,
                priority=Priority.IMMEDIATE,
                reasons=["第三根危险上影线", "放量跌破15分钟MA20"],
                next_step="清仓",
                cancel_condition="重新站回关键价位",
            )

            recorder.write_run(symbols=["002241"], decisions=[decision], notices=[])

            content = (Path(tmp) / "当日触发.md").read_text(encoding="utf-8")
            self.assertIn("# 当日触发", content)
            self.assertIn("| 时间 | 股票代码 | 卖出动作 | 分数 | 优先级 | 原因 | 建议 |", content)
            self.assertIn("002241", content)
            self.assertIn("第三根危险上影线；放量跌破15分钟MA20", content)

    def test_run_recorder_does_not_touch_daily_trigger_file_without_sell_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))

            recorder.write_run(symbols=["002241"], decisions=[], notices=[])

            self.assertFalse((Path(tmp) / "当日触发.md").exists())
