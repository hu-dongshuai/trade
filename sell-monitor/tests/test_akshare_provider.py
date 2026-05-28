from __future__ import annotations

import unittest
from datetime import datetime

import pandas as pd

from sell_monitor.data.akshare_provider import MarketDataError, _bars_from_dataframe, _filter_historical_m15_bars
from sell_monitor.domain.models import Bar


class AkshareProviderTest(unittest.TestCase):
    def test_bars_from_dataframe_supports_sina_minute_day_column(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "day": "2026-05-27 14:45:00",
                    "open": "9.210",
                    "high": "9.240",
                    "low": "9.200",
                    "close": "9.210",
                    "volume": "772400",
                    "amount": "7118787.9323",
                },
                {
                    "day": "2026-05-27 15:00:00",
                    "open": "9.220",
                    "high": "9.220",
                    "low": "9.190",
                    "close": "9.210",
                    "volume": "1711424",
                    "amount": "15756054.7557",
                },
            ]
        )

        bars = _bars_from_dataframe(df, limit=2)

        self.assertEqual(2, len(bars))
        self.assertEqual("2026-05-27 15:00:00", bars[-1].ts.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEqual(9.21, bars[-1].close)
        self.assertEqual(1711424.0, bars[-1].volume)

    def test_filter_historical_m15_bars_raises_when_online_source_is_too_new(self) -> None:
        bars = [
            Bar(datetime(2025, 11, 19, 14, 45, 0), 10.0, 10.2, 9.9, 10.1, 1000),
            Bar(datetime(2025, 11, 19, 15, 0, 0), 10.1, 10.3, 10.0, 10.2, 1200),
        ]

        with self.assertRaises(MarketDataError) as ctx:
            _filter_historical_m15_bars("002241", bars, datetime(2025, 10, 9, 15, 0, 0), limit=200)

        self.assertIn("最早仅到 2025-11-19 14:45:00", str(ctx.exception))
