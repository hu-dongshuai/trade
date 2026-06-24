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
            channel.send("[SellMonitor] 002241 exit_all score=6", "[002241] latest result")

            content = (Path(tmp) / "002241.md").read_text(encoding="utf-8")
            self.assertTrue(content.startswith("# 002241 监控记录"))
            self.assertLess(content.index("latest result"), content.index("first result"))

    def test_run_recorder_writes_compact_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))
            decision = Decision(
                symbol="002241",
                symbol_name="歌尔股份",
                action=Action.REDUCE,
                total_score=4,
                priority=Priority.HIGH,
                reasons=["测试原因"],
                next_step="减仓",
                cancel_condition="信号消失",
                current_price=28.27,
                hold_protection_score=3,
                hold_protection_reasons=["日线A级支撑保护", "向下流动性抓取后收回支撑"],
            )

            recorder.write_run(symbols=["002241"], decisions=[decision], notices=[])

            content = (Path(tmp) / "002241.md").read_text(encoding="utf-8")
            self.assertIn(
                "| 检测时间 | 股票代码 | 结论 | 动作 | 分数 | 价格 | 原因/提示 | 下一步 | 取消条件 |",
                content,
            )
            self.assertIn("| 歌尔股份 | 卖出信号 | reduce | 4 | 28.27 |", content)
            self.assertNotIn("股票名称", content)
            self.assertNotIn("持有保护", content)
            self.assertNotIn("high", content)

    def test_run_recorder_writes_compact_table_without_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))

            recorder.write_run(
                symbols=["002241"],
                decisions=[],
                notices=[],
                symbol_names={"002241": "歌尔股份"},
            )

            content = (Path(tmp) / "002241.md").read_text(encoding="utf-8")
            self.assertIn("| 歌尔股份 | 未触发卖出信号 | none | 0 | - |", content)

    def test_run_recorder_falls_back_to_symbol_when_name_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))

            recorder.write_run(
                symbols=["002241"],
                decisions=[],
                notices=[],
                symbol_names={},
            )

            content = (Path(tmp) / "002241.md").read_text(encoding="utf-8")
            self.assertIn("| 002241 | 未触发卖出信号 | none | 0 | - |", content)

    def test_run_recorder_filters_runtime_notices(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))
            decision = Decision(
                symbol="300015",
                symbol_name="爱尔眼科",
                action=Action.HOLD,
                total_score=0,
                priority=Priority.NORMAL,
                reasons=["未达到高质量卖出触发条件"],
                next_step="继续观察",
                cancel_condition="新增高质量卖出信号",
                current_price=12.34,
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

    def test_daily_trigger_summary_is_table_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))
            decision = Decision(
                symbol="002241",
                symbol_name="歌尔股份",
                action=Action.EXIT_ALL,
                total_score=6,
                priority=Priority.IMMEDIATE,
                reasons=["出现第三根危险上影线", "放量跌破15分钟MA20"],
                next_step="清仓",
                cancel_condition="重新站回关键价位",
                current_price=27.85,
                hold_protection_score=1,
                hold_protection_reasons=["当前更接近支撑而非压力"],
            )

            recorder.write_run(symbols=["002241"], decisions=[decision], notices=[])

            content = (Path(tmp) / "当日触发.md").read_text(encoding="utf-8")
            self.assertIn("| 时间 | 股票代码 | 卖出动作 | 分数 | 价格 | 原因 | 建议 |", content)
            self.assertIn("| 歌尔股份 | exit_all | 6 | 27.85 |", content)
            self.assertNotIn("## 2026-", content)
            self.assertNotIn("股票名称", content)
            self.assertNotIn("持有保护", content)

    def test_daily_trigger_summary_does_not_repeat_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))
            first = Decision(
                symbol="002241",
                symbol_name="歌尔股份",
                action=Action.EXIT_ALL,
                total_score=6,
                priority=Priority.IMMEDIATE,
                reasons=["第一次信号"],
                next_step="清仓",
                cancel_condition="信号消失",
                current_price=24.94,
            )
            second = Decision(
                symbol="002241",
                symbol_name="歌尔股份",
                action=Action.EXIT_ALL,
                total_score=6,
                priority=Priority.IMMEDIATE,
                reasons=["第二次信号"],
                next_step="清仓",
                cancel_condition="信号消失",
                current_price=24.95,
            )

            recorder.write_run(symbols=["002241"], decisions=[first], notices=[], now=datetime(2026, 6, 5, 9, 30, 0))
            recorder.write_run(symbols=["002241"], decisions=[second], notices=[], now=datetime(2026, 6, 5, 10, 30, 0))

            content = (Path(tmp) / "当日触发.md").read_text(encoding="utf-8")
            self.assertEqual(1, content.count("| 时间 | 股票代码 | 卖出动作 | 分数 | 价格 | 原因 | 建议 |"))
            self.assertEqual(1, content.count("| --- | --- | --- | ---: | ---: | --- | --- |"))
            self.assertLess(content.index("10:30:00"), content.index("09:30:00"))

    def test_zone_chart_stays_before_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))
            zone = PriceZone(
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
                symbol_names={"002241": "歌尔股份"},
                zone_snapshots={"002241": [zone]},
                daily_bar_snapshots={"002241": _daily_bars()},
            )

            content = (Path(tmp) / "002241.md").read_text(encoding="utf-8")
            self.assertLess(content.index("![002241 最新支撑压力图]"), content.index("| 检测时间 | 股票代码 |"))
            self.assertIn("<!-- SELL_MONITOR_LATEST_ZONES_END -->\n\n| 检测时间 |", content)


if __name__ == "__main__":
    unittest.main()
