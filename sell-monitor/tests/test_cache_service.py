from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sell_monitor.data.cache_service import FileMarketDataCache


class CacheServiceTest(unittest.TestCase):
    def test_ignores_empty_cached_bar_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileMarketDataCache(Path(tmp))
            cache.save_bars("002241", "15m", [])
            self.assertIsNone(cache.load_bars("002241", "15m"))
