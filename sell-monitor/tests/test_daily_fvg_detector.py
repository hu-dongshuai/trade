from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sell_monitor.domain.models import Bar
from sell_monitor.zones.daily_fvg_detector import detect_daily_fvg


class DailyFvgDetectorTest(unittest.TestCase):
    def test_detects_bearish_fvg(self) -> None:
        base = datetime(2026, 1, 1)
        bars = [
            Bar(base, 10.0, 10.8, 10.2, 10.7, 1000),
            Bar(base + timedelta(days=1), 10.7, 10.9, 9.8, 9.9, 2500),
            Bar(base + timedelta(days=2), 9.5, 10.1, 9.1, 9.2, 2000),
            Bar(base + timedelta(days=3), 9.2, 9.6, 8.9, 9.0, 1500),
        ]
        zones = detect_daily_fvg(bars)
        self.assertTrue(any("bearish_fvg" in zone.tags for zone in zones))


if __name__ == "__main__":
    unittest.main()

