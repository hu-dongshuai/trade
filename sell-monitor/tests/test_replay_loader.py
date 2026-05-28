from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sell_monitor.app.replay import _load_replay_market_data
from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.data.cache_service import FileMarketDataCache
from sell_monitor.data.fallback_provider import CachedFallbackMarketDataProvider
from sell_monitor.data.market_data_provider import StaticMarketDataProvider
from sell_monitor.domain.models import Bar


class _ReplayPrimaryFail:
    def get_daily_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200):
        raise MarketDataError("fail")

    def get_m15_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200):
        raise MarketDataError("fail")


class ReplayLoaderTest(unittest.TestCase):
    def test_load_replay_market_data_filters_to_as_of(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        provider = StaticMarketDataProvider(project_root / "examples" / "market_data.json")
        daily_bars, m15_bars, quote_price, quote_ts = _load_replay_market_data(
            provider,
            "TESTA",
            datetime(2026, 5, 27, 15, 0, 0),
        )
        self.assertTrue(daily_bars)
        self.assertTrue(m15_bars)
        self.assertLessEqual(m15_bars[-1].ts, datetime(2026, 5, 27, 15, 0, 0))
        self.assertEqual(m15_bars[-1].close, quote_price)
        self.assertEqual(m15_bars[-1].ts, quote_ts)

    def test_load_replay_market_data_uses_cached_fallback_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileMarketDataCache(Path(tmp))
            cache.save_bars(
                "002241",
                "1d",
                [
                    Bar(datetime(2026, 5, 19), 25.56, 25.83, 25.20, 25.72, 101405491),
                    Bar(datetime(2026, 5, 20), 25.50, 25.57, 25.02, 25.08, 90997007),
                ],
            )
            cache.save_bars(
                "002241",
                "15m",
                [
                    Bar(datetime(2026, 5, 20, 14, 45, 0), 25.30, 25.45, 25.18, 25.26, 1200000),
                    Bar(datetime(2026, 5, 20, 15, 0, 0), 25.26, 25.32, 25.08, 25.08, 980000),
                    Bar(datetime(2026, 5, 21, 9, 45, 0), 25.10, 25.30, 25.02, 25.18, 1500000),
                ],
            )
            provider = CachedFallbackMarketDataProvider(_ReplayPrimaryFail(), cache)

            daily_bars, m15_bars, quote_price, quote_ts = _load_replay_market_data(
                provider,
                "002241",
                datetime(2026, 5, 20, 15, 0, 0),
            )

            self.assertEqual(2, len(daily_bars))
            self.assertEqual(2, len(m15_bars))
            self.assertEqual(25.08, quote_price)
            self.assertEqual(datetime(2026, 5, 20, 15, 0, 0), quote_ts)
