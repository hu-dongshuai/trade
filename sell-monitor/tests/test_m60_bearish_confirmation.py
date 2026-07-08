from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sell_monitor.domain.models import Bar
from sell_monitor.signals.m60_bearish_confirmation import detect_m60_bearish_confirmation


def _expand_m60_to_m15(hourly_bars: list[tuple[float, float, float, float]]) -> list[Bar]:
    base = datetime(2026, 6, 1, 9, 30)
    result: list[Bar] = []
    for hour_idx, (open_, high, low, close) in enumerate(hourly_bars):
        for step in range(4):
            ts = base + timedelta(hours=hour_idx, minutes=15 * step)
            if step == 0:
                sub_open = open_
                sub_close = open_ + (close - open_) * 0.25
            elif step == 3:
                sub_open = open_ + (close - open_) * 0.75
                sub_close = close
            else:
                sub_open = open_ + (close - open_) * (step / 4)
                sub_close = open_ + (close - open_) * ((step + 1) / 4)
            result.append(Bar(ts, sub_open, high, low, sub_close, 1000))
    return result


class M60BearishConfirmationTest(unittest.TestCase):
    def test_requires_decisive_close_below_previous_low(self) -> None:
        hourly = [(12 - i * 0.05, 12.1 - i * 0.05, 11.9 - i * 0.05, 12 - i * 0.05) for i in range(20)]
        hourly.extend(
            [
                (11.0, 11.05, 10.7, 10.8),
                (10.82, 10.9, 10.72, 10.74),
            ]
        )

        signal = detect_m60_bearish_confirmation(_expand_m60_to_m15(hourly))

        self.assertIsNone(signal)

    def test_triggers_when_last_hour_breaks_previous_low_and_ma20(self) -> None:
        hourly = [(12 - i * 0.08, 12.08 - i * 0.08, 11.92 - i * 0.08, 12 - i * 0.08) for i in range(20)]
        hourly.extend(
            [
                (10.3, 10.35, 10.0, 10.05),
                (10.0, 10.02, 9.7, 9.72),
            ]
        )

        signal = detect_m60_bearish_confirmation(_expand_m60_to_m15(hourly))

        self.assertIsNotNone(signal)


if __name__ == "__main__":
    unittest.main()
