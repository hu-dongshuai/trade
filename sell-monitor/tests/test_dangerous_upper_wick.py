from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import Bar, PriceZone
from sell_monitor.signals.dangerous_upper_wick import detect_dangerous_upper_wick_signals


class DangerousUpperWickTest(unittest.TestCase):
    def test_counts_two_dangerous_upper_wicks(self) -> None:
        zone = PriceZone("zone", "15m", 103.0, 103.6, score=4, level=ZoneLevel.B, tags=["resistance"])
        base = datetime(2026, 5, 27, 9, 30)
        bars: list[Bar] = []
        for idx in range(12):
            bars.append(
                Bar(
                    ts=base + timedelta(minutes=15 * idx),
                    open=102.0,
                    high=102.4,
                    low=101.9,
                    close=102.2,
                    volume=100000,
                )
            )
        bars.append(Bar(base + timedelta(minutes=180), 103.2, 103.7, 102.95, 103.0, 250000))
        bars.append(Bar(base + timedelta(minutes=195), 103.0, 103.1, 102.7, 102.9, 110000))
        bars.append(Bar(base + timedelta(minutes=210), 102.9, 103.62, 102.62, 102.78, 260000))
        signals = detect_dangerous_upper_wick_signals(bars, zone)
        names = {signal.name for signal in signals}
        self.assertIn("first_dangerous_upper_wick", names)
        self.assertIn("second_dangerous_upper_wick", names)


if __name__ == "__main__":
    unittest.main()

