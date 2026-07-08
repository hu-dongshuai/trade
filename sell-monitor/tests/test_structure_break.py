from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sell_monitor.domain.models import Bar
from sell_monitor.signals.structure_break import detect_structure_break


class StructureBreakTest(unittest.TestCase):
    def test_requires_buffer_below_structure_low(self) -> None:
        start = datetime(2026, 6, 1, 9, 30)
        bars = [
            Bar(start + timedelta(minutes=15 * 0), 10.0, 10.2, 9.9, 10.1, 1000),
            Bar(start + timedelta(minutes=15 * 1), 10.1, 10.25, 9.95, 10.0, 1000),
            Bar(start + timedelta(minutes=15 * 2), 10.0, 10.05, 9.85, 9.92, 1000),
            Bar(start + timedelta(minutes=15 * 3), 9.92, 10.4, 9.9, 10.3, 1100),
            Bar(start + timedelta(minutes=15 * 4), 10.3, 10.7, 10.1, 10.6, 1200),
            Bar(start + timedelta(minutes=15 * 5), 10.6, 10.45, 10.0, 10.05, 900),
            Bar(start + timedelta(minutes=15 * 6), 10.05, 10.1, 9.84, 9.84, 1500),
        ]

        signal = detect_structure_break(bars)

        self.assertIsNone(signal)

    def test_triggers_when_decisively_below_structure_low(self) -> None:
        start = datetime(2026, 6, 1, 9, 30)
        bars = [
            Bar(start + timedelta(minutes=15 * 0), 10.0, 10.2, 9.9, 10.1, 1000),
            Bar(start + timedelta(minutes=15 * 1), 10.1, 10.25, 9.95, 10.0, 1000),
            Bar(start + timedelta(minutes=15 * 2), 10.0, 10.05, 9.85, 9.92, 1000),
            Bar(start + timedelta(minutes=15 * 3), 9.92, 10.4, 9.9, 10.3, 1100),
            Bar(start + timedelta(minutes=15 * 4), 10.3, 10.7, 10.1, 10.6, 1200),
            Bar(start + timedelta(minutes=15 * 5), 10.6, 10.45, 10.0, 10.05, 900),
            Bar(start + timedelta(minutes=15 * 6), 10.05, 10.1, 9.78, 9.78, 1500),
        ]

        signal = detect_structure_break(bars)

        self.assertIsNotNone(signal)


if __name__ == "__main__":
    unittest.main()
