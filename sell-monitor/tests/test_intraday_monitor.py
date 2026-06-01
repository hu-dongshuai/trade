from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sell_monitor.domain.models import Bar
from sell_monitor.monitor.intraday_monitor import detect_m15_ma20_high_volume_break


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


if __name__ == "__main__":
    unittest.main()
