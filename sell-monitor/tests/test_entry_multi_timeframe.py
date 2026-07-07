from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sell_monitor.domain.models import Bar
from sell_monitor.entry.multi_timeframe import build_weekly_entry_view


def _bar(day: datetime, open_: float, high: float, low: float, close: float, volume: float) -> Bar:
    return Bar(ts=day, open=open_, high=high, low=low, close=close, volume=volume)


class EntryMultiTimeframeTest(unittest.TestCase):
    def test_build_weekly_entry_view_returns_strong_background_near_support(self) -> None:
        start = datetime(2025, 1, 6)
        bars: list[Bar] = []
        price = 10.0
        for week in range(20):
            for day in range(5):
                ts = start + timedelta(days=week * 7 + day)
                open_ = price + 0.05
                low = price - 0.10
                high = price + 0.35
                close = price + 0.20
                volume = 1000 - week * 10
                bars.append(_bar(ts, open_, high, low, close, volume))
            price += 0.25

        for offset in range(5):
            ts = start + timedelta(days=20 * 7 + offset)
            bars.append(_bar(ts, 14.9, 15.2, 14.6, 15.1, 700))

        supports, resistances, background, score, reasons = build_weekly_entry_view(bars, 15.0, True)
        self.assertIn(background, {"A", "B"})
        self.assertGreaterEqual(score, 4)
        self.assertTrue(any("周线" in reason for reason in reasons))
        self.assertIsInstance(supports, list)
        self.assertIsInstance(resistances, list)

    def test_build_weekly_entry_view_returns_c_when_weekly_is_weak(self) -> None:
        start = datetime(2025, 1, 6)
        bars: list[Bar] = []
        price = 20.0
        for week in range(24):
            for day in range(5):
                ts = start + timedelta(days=week * 7 + day)
                open_ = price - 0.05
                high = price + 0.10
                low = price - 0.40
                close = price - 0.25
                volume = 1500 + week * 15
                bars.append(_bar(ts, open_, high, low, close, volume))
            price -= 0.20

        _, _, background, score, reasons = build_weekly_entry_view(bars, bars[-1].close, False)
        self.assertEqual("C", background)
        self.assertLessEqual(score, 4)
        self.assertTrue(reasons)


if __name__ == "__main__":
    unittest.main()
