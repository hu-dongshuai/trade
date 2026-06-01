from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sell_monitor.config import ObsidianMonitorConfig
from sell_monitor.domain.enums import Action, Priority, ZoneLevel
from sell_monitor.domain.models import Bar, Decision, PriceZone
from sell_monitor.notifier.channels.obsidian import ObsidianMarkdownChannel, ObsidianMonitorRunRecorder


def _daily_bars(count: int = 30) -> list[Bar]:
    start = datetime(2026, 1, 1)
    return [
        Bar(
            ts=start + timedelta(days=idx),
            open=20 + idx * 0.1,
            high=21 + idx * 0.1,
            low=19 + idx * 0.1,
            close=20.5 + idx * 0.1,
            volume=1000,
        )
        for idx in range(count)
    ]


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
                notices=["[002241] 未接近日线 A/B/C 压力位，暂不启动 15 分钟监测"],
            )

            first = (Path(tmp) / "002241.md").read_text(encoding="utf-8")
            second = (Path(tmp) / "002739.md").read_text(encoding="utf-8")
            self.assertIn("| 检测时间 | 股票代码 | 结论 | 动作 | 分数 | 优先级 | 原因/提示 | 下一步 | 取消条件 |", first)
            self.assertIn("未触发卖出信号", first)
            self.assertIn("[002241] 未接近日线 A/B/C 压力位", first)
            self.assertIn("未触发卖出信号", second)
            self.assertNotIn("[002241] 未接近日线 A/B/C 压力位", second)

    def test_run_recorder_filters_runtime_notices_from_reason_cell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))
            decision = Decision(
                symbol="300015",
                action=Action.HOLD,
                total_score=0,
                priority=Priority.NORMAL,
                reasons=["未达到高质量卖出触发条件"],
                next_step="继续观察",
                cancel_condition="新增高质量卖出信号",
            )

            recorder.write_run(
                symbols=["300015"],
                decisions=[decision],
                notices=[
                    "[300015] 已命中本地缓存历史15分钟数据（截至 2026-05-28 14:00:00）",
                    "[300015] 回溯补齐检测记录（截至 2026-05-28 14:00:00）",
                ],
            )

            content = (Path(tmp) / "300015.md").read_text(encoding="utf-8")
            self.assertIn("未达到高质量卖出触发条件", content)
            self.assertNotIn("已命中本地缓存历史15分钟数据", content)
            self.assertNotIn("回溯补齐检测记录", content)

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
            self.assertNotIn("```text", content)

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

    def test_run_recorder_keeps_only_latest_zone_table_near_top(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))
            zone = PriceZone(
                name="daily_resistance",
                timeframe="1d",
                low=27.8,
                high=28.6,
                score=7,
                level=ZoneLevel.A,
                tags=["resistance", "with_fvg"],
                touches=3,
                importance_score=8,
                fragility_score=1,
                invalidation_price=28.9,
            )

            recorder.write_run(
                symbols=["002241"],
                decisions=[],
                notices=[],
                zone_snapshots={"002241": [zone]},
                daily_bar_snapshots={"002241": _daily_bars()},
            )
            newer_zone = PriceZone(
                name="weekly_resistance",
                timeframe="1w",
                low=31.6,
                high=32.4,
                score=6,
                level=ZoneLevel.B,
                tags=["resistance", "weekly_resistance"],
                touches=2,
                importance_score=7,
                fragility_score=1,
                invalidation_price=32.8,
            )
            recorder.write_run(
                symbols=["002241"],
                decisions=[],
                notices=[],
                zone_snapshots={"002241": [newer_zone]},
                daily_bar_snapshots={"002241": _daily_bars()},
            )

            content = (Path(tmp) / "002241.md").read_text(encoding="utf-8")
            self.assertLess(content.index("![002241 最新支撑压力图]"), content.index("| 检测时间 | 股票代码 |"))
            self.assertIn("<!-- SELL_MONITOR_LATEST_ZONES_END -->\n\n| 检测时间", content)
            self.assertIn("assets/002241_latest_zones.svg", content)
            self.assertTrue((Path(tmp) / "assets" / "002241_latest_zones.svg").exists())
            self.assertNotIn("27.80 | 28.60", content)
            self.assertEqual(0, content.count("### 支撑压力位"))
            self.assertEqual(0, content.count("## 监控记录"))
            self.assertEqual(1, content.count("| 检测时间 | 股票代码 |"))
            self.assertEqual(2, content.count("| 002241 | 未触发卖出信号 |"))

    def test_run_recorder_removes_old_embedded_zone_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "002241.md"
            path.write_text(
                "# 002241 监控记录\n\n"
                "## 监控记录\n\n"
                "### 支撑压力位\n\n"
                "| 股票 | 周期 | 等级 | 类型 | 区间下沿 | 区间上沿 | 净分 | 重要性 | 脆弱性 | 失效价 | 触达次数 | 标签 |\n"
                "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |\n"
                "| 002241 | 1d | A | 压力 | 27.80 | 28.60 | 7 | 8 | 1 | 28.90 | 3 | old |\n\n"
                "| 检测时间 | 股票代码 | 结论 | 动作 | 分数 | 优先级 | 原因/提示 | 下一步 | 取消条件 |\n"
                "| --- | --- | --- | --- | ---: | --- | --- | --- | --- |\n"
                "| 2026-05-28 10:30:00 | 002241 | 未触发卖出信号 | none | 0 | normal | old | 继续观察 | - |\n\n"
                "```text\nold detail\n```\n",
                encoding="utf-8",
            )
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))

            recorder.write_run(
                symbols=["002241"],
                decisions=[],
                notices=[],
                zone_snapshots={"002241": []},
                daily_bar_snapshots={"002241": _daily_bars()},
            )

            content = path.read_text(encoding="utf-8")
            self.assertNotIn("| 002241 | 1d | A | 压力 | 27.80 | 28.60", content)
            self.assertEqual(0, content.count("### 支撑压力位"))
            self.assertEqual(1, content.count("| 检测时间 | 股票代码 |"))
            self.assertIn("2026-05-28 10:30:00", content)
            self.assertNotIn("```text", content)
            self.assertNotIn("old detail", content)

    def test_run_recorder_can_write_historical_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))

            recorder.write_run(
                symbols=["002241"],
                decisions=[],
                notices=[],
                now=datetime(2026, 5, 28, 10, 30, 0),
            )

            content = (Path(tmp) / "002241.md").read_text(encoding="utf-8")
            self.assertIn("2026-05-28 10:30:00", content)
