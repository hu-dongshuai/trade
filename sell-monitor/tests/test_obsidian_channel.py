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
            self.assertTrue(content.startswith("---\ncssclasses: full-width-note\n---\n\n# 002241 监控记录"))
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

    def test_run_recorder_repairs_legacy_mojibake_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "002241.md"
            path.write_text(
                "---\ncssclasses: full-width-note\n---\n\n"
                "# 1. 閻╂垶甯剁拋鏉跨秿\n\n"
                "| 妫€娴嬫椂闂? | 鑲＄エ浠ｇ爜 | 缁撹 | 鍔ㄤ綔 | 鍒嗘暟 | 浠锋牸 | 鍘熷洜/鎻愮ず | 涓嬩竴姝? | 鍙栨秷鏉′欢 | 澶嶇洏 |\n"
                "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- |\n"
                "| 2026-07-06 15:00:00 | 姝屽皵鑲′唤 | 鍗栧嚭淇″彿 | reduce | 5 | 21.47 | 娴嬭瘯鍘熷洜 | 鍑忎粨 | 淇″彿娑堝け | 寰呭鐩? |\n",
                encoding="utf-8",
            )

            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))
            recorder.write_run(
                symbols=["002241"],
                decisions=[],
                notices=[],
                symbol_names={"002241": "歌尔股份"},
            )

            content = path.read_text(encoding="utf-8")
            self.assertIn("# 002241 监控记录", content)
            self.assertIn("| 检测时间 | 股票代码 | 结论 | 动作 | 分数 | 价格 | 原因/提示 | 下一步 | 取消条件 | 复盘 |", content)
            self.assertIn("歌尔股份", content)
            self.assertNotIn("妫€娴", content)
            self.assertNotIn("姝屽皵", content)

    def test_daily_trigger_summary_is_written_cleanly(self) -> None:
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
            self.assertNotIn("褰撴棩", content)

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

    def test_focus_support_and_resistance_are_written_before_chart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianMonitorRunRecorder(ObsidianMonitorConfig(monitor_dir=Path(tmp)))
            decision = Decision(
                symbol="002241",
                symbol_name="歌尔股份",
                action=Action.HOLD,
                total_score=0,
                priority=Priority.NORMAL,
                reasons=["test"],
                next_step="观察",
                cancel_condition="-",
                current_price=28.0,
            )
            zones = [
                PriceZone(name="support", timeframe="1d", low=27.2, high=27.8, level=ZoneLevel.B, tags=["support"], importance_score=8, score=7),
                PriceZone(name="resistance", timeframe="1d", low=29.1, high=29.8, level=ZoneLevel.A, tags=["resistance"], importance_score=9, score=8),
            ]

            recorder.write_run(
                symbols=["002241"],
                decisions=[decision],
                notices=[],
                symbol_names={"002241": "歌尔股份"},
                zone_snapshots={"002241": zones},
                daily_bar_snapshots={"002241": _daily_bars()},
            )

            content = (Path(tmp) / "002241.md").read_text(encoding="utf-8")
            self.assertIn("当前最需要关注的支撑/压力位", content)
            self.assertIn("支撑位：日线B级支撑区 27.20-27.80", content)
            self.assertIn("压力位：日线A级压力区 29.10-29.80", content)
            self.assertLess(content.index("当前最需要关注的支撑/压力位"), content.index("<img"))

    def test_legacy_daily_trigger_file_is_migrated_on_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            monitor_dir = Path(tmp)
            legacy = monitor_dir / "当天触发.md"
            legacy.write_text(
                "---\ncssclasses: full-width-note\n---\n\n"
                "# 褰撴棩瑙﹀彂\n\n"
                "| 鏃堕棿 | 鑲＄エ浠ｇ爜 | 鍗栧嚭鍔ㄤ綔 | 鍒嗘暟 | 浠锋牸 | 鍘熷洜 | 寤鸿 | 澶嶇洏 |\n"
                "| --- | --- | --- | ---: | ---: | --- | --- | --- |\n"
                "| 2026-06-25 09:30:00 | 002241 | reduce | 5 | 25.10 | 鏃ц褰? | 瑙傚療 | 寰呭鐩? |\n",
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
                cancel_condition="信号消失",
                current_price=31.25,
            )

            recorder.write_run(symbols=["300014"], decisions=[decision], notices=[])

            content = (monitor_dir / "当日应卖出.md").read_text(encoding="utf-8")
            self.assertIn("002241", content)
            self.assertIn("亿纬锂能", content)
            self.assertNotIn("褰撳ぉ", content)


if __name__ == "__main__":
    unittest.main()
