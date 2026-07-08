from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sell_monitor.domain.models import Bar
from sell_monitor.monitor.sell_warning_state import evaluate_sell_warning_state


class SellWarningStateTest(unittest.TestCase):
    def test_enters_warning_state_when_daily_and_m60_turn_weak(self) -> None:
        daily_bars = []
        start = datetime(2026, 5, 1)
        closes = [10, 10.4, 10.8, 11.0, 11.2, 11.1, 10.9, 10.6, 10.3, 10.0, 9.8, 9.7, 9.6, 9.5, 9.4, 9.3, 9.2, 9.15, 9.1, 9.05, 9.0, 8.95, 8.9, 8.85, 8.8, 8.75]
        for idx, close in enumerate(closes):
            ts = start + timedelta(days=idx)
            daily_bars.append(Bar(ts, close + 0.1, close + 0.2, close - 0.2, close, 1000 + idx * 10))

        m15_bars = []
        base = datetime(2026, 6, 1, 9, 30)
        prices = [
            10.0, 10.1, 10.2, 10.25,
            10.2, 10.1, 10.0, 9.95,
            9.9, 9.85, 9.8, 9.75,
            9.72, 9.68, 9.62, 9.58,
            9.56, 9.54, 9.5, 9.45,
            9.44, 9.4, 9.36, 9.3,
            9.28, 9.25, 9.2, 9.15,
            9.14, 9.12, 9.08, 9.0,
            8.98, 8.96, 8.92, 8.86,
            8.84, 8.82, 8.78, 8.72,
            8.7, 8.69, 8.65, 8.6,
            8.58, 8.55, 8.5, 8.45,
            8.44, 8.42, 8.38, 8.32,
            8.3, 8.28, 8.24, 8.18,
            8.16, 8.12, 8.08, 8.0,
            7.98, 7.95, 7.9, 7.84,
            7.82, 7.8, 7.76, 7.7,
            7.68, 7.66, 7.62, 7.56,
            7.54, 7.5, 7.46, 7.4,
            7.38, 7.34, 7.3, 7.24,
            7.22, 7.18, 7.14, 7.08,
        ]
        for idx, close in enumerate(prices):
            ts = base + timedelta(minutes=15 * idx)
            m15_bars.append(Bar(ts, close + 0.04, close + 0.06, close - 0.08, close, 2000 - idx * 5))

        active, reasons = evaluate_sell_warning_state(daily_bars, m15_bars)

        self.assertTrue(active)
        self.assertGreaterEqual(len(reasons), 2)


if __name__ == "__main__":
    unittest.main()
