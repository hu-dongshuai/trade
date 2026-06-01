from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sell_monitor.data.cache_service import FileMarketDataCache
from sell_monitor.domain.models import Bar


class CacheServiceTest(unittest.TestCase):
    def test_ignores_empty_cached_bar_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileMarketDataCache(Path(tmp))
            cache.save_bars("002241", "15m", [])
            self.assertIsNone(cache.load_bars("002241", "15m"))

    def test_merge_save_bars_preserves_existing_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileMarketDataCache(Path(tmp))
            cache.save_bars(
                "002241",
                "15m",
                [
                    Bar(datetime(2026, 5, 20, 9, 30), 10, 11, 9, 10.5, 100),
                    Bar(datetime(2026, 5, 20, 9, 45), 10.5, 11, 10, 10.8, 110),
                ],
            )

            cache.merge_save_bars(
                "002241",
                "15m",
                [
                    Bar(datetime(2026, 5, 20, 9, 45), 10.6, 11.2, 10.2, 10.9, 120),
                    Bar(datetime(2026, 5, 20, 10, 0), 10.9, 11.3, 10.7, 11.0, 130),
                ],
            )

            bars = cache.load_bars("002241", "15m")
            self.assertIsNotNone(bars)
            self.assertEqual(3, len(bars))
            self.assertEqual(datetime(2026, 5, 20, 9, 30), bars[0].ts)
            self.assertEqual(10.9, bars[1].close)
