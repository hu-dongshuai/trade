from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from sell_monitor.trading_time import is_a_share_trading_time


class TradingTimeTest(unittest.TestCase):
    def test_accepts_weekday_morning_and_afternoon_sessions(self) -> None:
        tz = ZoneInfo("Asia/Shanghai")

        self.assertTrue(is_a_share_trading_time(datetime(2026, 5, 28, 9, 30, tzinfo=tz)))
        self.assertTrue(is_a_share_trading_time(datetime(2026, 5, 28, 11, 30, tzinfo=tz)))
        self.assertTrue(is_a_share_trading_time(datetime(2026, 5, 28, 13, 0, tzinfo=tz)))
        self.assertTrue(is_a_share_trading_time(datetime(2026, 5, 28, 15, 0, tzinfo=tz)))

    def test_rejects_lunch_break_after_hours_and_weekends(self) -> None:
        tz = ZoneInfo("Asia/Shanghai")

        self.assertFalse(is_a_share_trading_time(datetime(2026, 5, 28, 9, 29, tzinfo=tz)))
        self.assertFalse(is_a_share_trading_time(datetime(2026, 5, 28, 11, 31, tzinfo=tz)))
        self.assertFalse(is_a_share_trading_time(datetime(2026, 5, 28, 15, 1, tzinfo=tz)))
        self.assertFalse(is_a_share_trading_time(datetime(2026, 5, 30, 10, 0, tzinfo=tz)))


if __name__ == "__main__":
    unittest.main()
