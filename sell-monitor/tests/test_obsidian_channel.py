from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sell_monitor.config import ObsidianMonitorConfig
from sell_monitor.domain.enums import Action, Priority, ZoneLevel
from sell_monitor.domain.models import AlertReviewRecord, Bar, Decision, PriceZone
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
            self.assertTrue(content.startswith("---\ncssclasses: full-width-note\n---\n\n# 002241"))
            self.assertLess(content.index("latest result"), content.index("first result"))

    def test_run_recorder_writes_review_column_for_sell_signal(self) -> None:
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
            self.assertIn("待复盘", content)
            self.assertIn("歌尔股份", content)
            self.assertIn("28.27", content)

    def test_run_recorder_writes_hold_row_without_review_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))

            recorder.write_run(
                symbols=["002241"],
                decisions=[],
                notices=[],
                symbol_names={"002241": "歌尔股份"},
            )

            content = (Path(tmp) / "002241.md").read_text(encoding="utf-8")
            self.assertIn("歌尔股份", content)
            self.assertIn("none", content)

    def test_daily_trigger_summary_is_written_to_when_day_should_sell(self) -> None:
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
                cancel_condition="重新站回关键位",
                current_price=27.85,
            )

            recorder.write_run(symbols=["002241"], decisions=[decision], notices=[])

            content = (Path(tmp) / "当日应卖出.md").read_text(encoding="utf-8")
            self.assertIn("# 当日应卖出", content)
            self.assertIn("歌尔股份", content)
            self.assertIn("27.85", content)
            self.assertNotIn("## 2026-", content)

    def test_apply_review_updates_marks_false_positive_in_symbol_and_daily_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))
            now = datetime(2026, 6, 24, 10, 30, 0)
            decision = Decision(
                symbol="002241",
                symbol_name="歌尔股份",
                action=Action.EXIT_ALL,
                total_score=8,
                priority=Priority.IMMEDIATE,
                reasons=["出现第三根危险上影线", "放量跌破15分钟MA20"],
                next_step="清仓",
                cancel_condition="重新站回关键位",
                current_price=24.90,
            )

            recorder.write_run(symbols=["002241"], decisions=[decision], notices=[], now=now)
            review = AlertReviewRecord(
                alert_id="002241:2026-06-24T10:30:00:exit_all",
                symbol="002241",
                symbol_name="歌尔股份",
                action=Action.EXIT_ALL,
                alert_ts=now,
                price=24.90,
                score=8,
                reasons=["出现第三根危险上影线"],
                review_status="false_positive",
                reviewed_at=datetime(2026, 7, 1, 15, 0, 0),
                drawdown_pct=2.10,
                runup_pct=9.35,
            )

            recorder.apply_review_updates([review])

            symbol_content = (Path(tmp) / "002241.md").read_text(encoding="utf-8")
            daily_content = (Path(tmp) / "当日应卖出.md").read_text(encoding="utf-8")
            self.assertIn("误报", symbol_content)
            self.assertIn("误报", daily_content)
            self.assertNotIn("待复盘", symbol_content)

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
            self.assertIn('style="width: 40%; max-width: 40%;"', content)
            self.assertLess(content.index("<img"), content.index("|"))

    def test_legacy_daily_trigger_file_is_migrated_on_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            monitor_dir = Path(tmp)
            legacy = monitor_dir / "当天触发.md"
            legacy.write_text(
                "# 当日触发\n\n"
                "| 时间 | 股票代码 | 卖出动作 | 分数 | 价格 | 原因 | 建议 | 复盘 |\n"
                "| --- | --- | --- | ---: | ---: | --- | --- | --- |\n"
                "| 2026-06-25 09:30:00 | 002241 | reduce | 5 | 25.10 | 旧记录 | 观察 | 待复盘 |\n",
                encoding="utf-8",
            )
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=monitor_dir))
            decision = Decision(
                symbol="300014",
                symbol_name="亿纬锂能",
                action=Action.REDUCE,
                total_score=6,
                priority=Priority.HIGH,
                reasons=["新记录"],
                next_step="减仓",
                cancel_condition="无",
                current_price=31.25,
            )

            recorder.write_run(symbols=["300014"], decisions=[decision], notices=[])

            content = (monitor_dir / "当日应卖出.md").read_text(encoding="utf-8")
            self.assertIn("002241", content)
            self.assertIn("亿纬锂能", content)


if __name__ == "__main__":
    unittest.main()
