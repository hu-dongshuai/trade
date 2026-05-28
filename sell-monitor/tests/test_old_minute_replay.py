from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.data.cache_service import FileMarketDataCache
from sell_monitor.data.fallback_provider import CachedFallbackMarketDataProvider


class _PrimaryTooNew:
    def get_m15_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200):
        raise MarketDataError(
            f"[{symbol}] 已尝试拉取旧分钟数据，但当前可用在线15分钟数据最早仅到 2025-11-19 14:45:00，无法覆盖 "
            f"{end_dt.strftime('%Y-%m-%d %H:%M:%S')}。"
        )


class OldMinuteReplayTest(unittest.TestCase):
    def test_preserves_underlying_old_minute_error_without_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = CachedFallbackMarketDataProvider(_PrimaryTooNew(), FileMarketDataCache(Path(tmp)))
            with self.assertRaises(MarketDataError) as ctx:
                provider.get_m15_bars_until("002241", datetime(2025, 10, 9, 15, 0, 0), limit=200)
            self.assertIn("最早仅到 2025-11-19 14:45:00", str(ctx.exception))
