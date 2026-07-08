from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sell_monitor.domain.models import Bar
from sell_monitor.monitor.intraday_monitor import (
    detect_m15_ma20_high_volume_break,
    detect_next_day_tail_break_confirmation,
)


class IntradayMonitorTest(unittest.TestCase):
    def test_detects_high_volume_break_below_m15_ma20(self) -> None:
        start = datetime(2026, 5, 28, 9, 30)
        bars = [
            Bar(
                ts=start + timedelta(minutes=15 * idx),
                open=100,
                high=101,
                low=99,
                close=100,
                volume=1000,
            )
            for idx in range(20)
        ]
        bars.append(
            Bar(
                ts=start + timedelta(minutes=15 * 20),
                open=100,
                high=100.2,
                low=98,
                close=99,
                volume=1000,
            )
        )
        bars.append(
            Bar(
                ts=start + timedelta(minutes=15 * 21),
                open=99,
                high=100.2,
                low=96,
                close=97,
                volume=2000,
            )
        )

        signal = detect_m15_ma20_high_volume_break(bars)

        self.assertIsNotNone(signal)
        self.assertEqual("m15_ma20_high_volume_break", signal.name)
        self.assertIn("14:45", signal.reason)

    def test_ignores_single_bar_break_below_m15_ma20(self) -> None:
        start = datetime(2026, 5, 28, 9, 30)
        bars = [
            Bar(
                ts=start + timedelta(minutes=15 * idx),
                open=100,
                high=101,
                low=99,
                close=100,
                volume=1000,
            )
            for idx in range(21)
        ]
        bars.append(
            Bar(
                ts=start + timedelta(minutes=15 * 21),
                open=100,
                high=100.2,
                low=96,
                close=97,
                volume=2000,
            )
        )

        signal = detect_m15_ma20_high_volume_break(bars)

        self.assertIsNone(signal)

    def test_detects_next_day_confirmation_after_tail_end_resonance_break(self) -> None:
        bars: list[Bar] = []
        baseline_days = [
            (datetime(2026, 5, 28, 9, 30), [100.0] * 16),
            (datetime(2026, 5, 29, 9, 30), [100.1] * 16),
        ]
        for start, closes in baseline_days:
            for idx, close in enumerate(closes):
                ts = start + timedelta(minutes=15 * idx)
                bars.append(Bar(ts=ts, open=close, high=close + 0.2, low=close - 0.2, close=close, volume=1000))

        start = datetime(2026, 6, 1, 9, 30)
        day1_closes = [
            100.0,
            100.1,
            99.9,
            100.0,
            100.1,
            100.0,
            100.1,
            100.0,
            100.1,
            100.2,
            100.15,
            100.1,
            100.05,
            99.9,
            99.3,
            98.7,
        ]
        for idx, close in enumerate(day1_closes):
            ts = start + timedelta(minutes=15 * idx)
            open_ = day1_closes[idx - 1] if idx else close
            high = max(open_, close) + 0.2
            low = min(open_, close) - 0.2
            volume = 1000
            if idx == 15:
                high = 99.5
                low = 98.4
                volume = 2200
            bars.append(Bar(ts=ts, open=open_, high=high, low=low, close=close, volume=volume))

        day2_start = datetime(2026, 6, 2, 9, 30)
        day2_specs = [
            (98.6, 98.7, 98.2, 98.4, 1100),
            (98.4, 98.5, 98.1, 98.3, 1050),
            (98.3, 98.35, 98.0, 98.1, 1080),
            (98.1, 98.2, 97.9, 98.0, 1200),
        ]
        for idx, (open_, high, low, close, volume) in enumerate(day2_specs):
            bars.append(Bar(ts=day2_start + timedelta(minutes=15 * idx), open=open_, high=high, low=low, close=close, volume=volume))

        signal = detect_next_day_tail_break_confirmation(bars)

        self.assertIsNotNone(signal)
        self.assertEqual("next_day_tail_break_confirmation", signal.name)
        self.assertIn("10:15", signal.reason)


if __name__ == "__main__":
    unittest.main()
