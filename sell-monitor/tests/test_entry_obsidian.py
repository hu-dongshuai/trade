from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sell_monitor.config import ObsidianEntryConfig
from sell_monitor.domain.enums import EntryAction
from sell_monitor.domain.models import Bar, EntryDecision, PriceZone
from sell_monitor.notifier.channels.entry_obsidian import ObsidianEntryRunRecorder


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


class EntryObsidianRecorderTest(unittest.TestCase):
    def test_writes_lightweight_html_table_markup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorder = ObsidianEntryRunRecorder(ObsidianEntryConfig(monitor_dir=Path(tmp)))
            decision = EntryDecision(
                symbol="002241",
                symbol_name="歌尔股份",
                action=EntryAction.ALLOW_ENTRY,
                allowed=True,
                entry_score=7,
                entry_route="standard_entry",
                entry_model="pullback_buy",
                planned_entry_price=24.80,
                stop_loss_price=24.10,
                first_take_profit_price=26.90,
                risk_reward_ratio=2.10,
                reasons=["日线趋势健康", "接近A级支撑", "15分钟承接确认"],
                blocking_reasons=[],
                next_step="按标准开仓计划执行",
            )
            zone = PriceZone(name="support", timeframe="1d", low=24.2, high=24.9, tags=["support"])

            recorder.write_run(
                symbols=["002241"],
                decisions=[decision],
                notices=[],
                zone_snapshots={"002241": [zone]},
                daily_bar_snapshots={"002241": _daily_bars()},
            )

            content = (Path(tmp) / "002241.md").read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---\ncssclasses: full-width-note\n---\n\n"))
            self.assertIn("<!-- ENTRY_MONITOR_TABLE_START -->", content)
            self.assertIn('<table class="trade-monitor-table entry-monitor-table">', content)
            self.assertNotIn("<colgroup>", content)
            self.assertIn('class="trade-monitor-alert-time"', content)
            self.assertIn("pullback_buy", content)
            self.assertIn("歌尔股份", content)

    def test_migrates_existing_markdown_rows_into_html_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "002241.md"
            path.write_text(
                "# 002241 开仓检查记录\n"
                "| 检测时间 | 股票代码 | 是否允许开仓 | 开仓路线/模型 | 开仓分数 | 计划挂单价 | 止损价 | 第一止盈位 | 盈亏比 | 原因/阻断原因 | 下一步建议 |\n"
                "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |\n"
                "| 2026-07-02 10:30:00 | 002241 | 不允许 | 禁止回补 / none | 0 | - | - | - | - | 未识别出明确开仓模型 | 继续观察 |\n",
                encoding="utf-8",
            )

            recorder = ObsidianEntryRunRecorder(ObsidianEntryConfig(monitor_dir=Path(tmp)))
            recorder.write_run(symbols=["002241"], decisions=[], notices=[])

            content = path.read_text(encoding="utf-8")
            self.assertIn("<!-- ENTRY_MONITOR_TABLE_START -->", content)
            self.assertIn("<tbody>", content)
            self.assertIn("2026-07-02 10:30:00", content)
            self.assertNotIn("| 检测时间 | 股票代码 |", content)


if __name__ == "__main__":
    unittest.main()
