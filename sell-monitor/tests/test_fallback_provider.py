from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.data.cache_service import FileMarketDataCache
from sell_monitor.data.fallback_provider import CachedFallbackMarketDataProvider
from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import Bar, PriceZone, Quote


class _PrimaryOk:
    def get_latest_quote(self, symbol: str) -> Quote:
        return Quote(symbol=symbol, price=10.5, ts=datetime(2026, 5, 27, 15, 0, 0))

    def get_daily_bars(self, symbol: str, limit: int = 200) -> list[Bar]:
        return [Bar(datetime(2026, 5, 27), 10, 11, 9.8, 10.5, 1000)]

    def get_m15_bars(self, symbol: str, limit: int = 200) -> list[Bar]:
        return [Bar(datetime(2026, 5, 27, 15, 0, 0), 10.2, 10.6, 10.1, 10.5, 200)]

    def get_daily_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200) -> list[Bar]:
        return [Bar(datetime(2026, 5, 20), 10, 11, 9.8, 10.5, 1000)]

    def get_m15_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200) -> list[Bar]:
        return [Bar(datetime(2026, 5, 20, 15, 0, 0), 10.2, 10.6, 10.1, 10.5, 200)]

    def get_market_state(self) -> str:
        return "neutral"

    def get_sector_state(self, symbol: str) -> str:
        return "neutral"


class _PrimaryFail:
    def get_latest_quote(self, symbol: str):
        raise MarketDataError("fail")

    def get_daily_bars(self, symbol: str, limit: int = 200):
        raise MarketDataError("fail")

    def get_m15_bars(self, symbol: str, limit: int = 200):
        raise MarketDataError("fail")

    def get_daily_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200):
        raise MarketDataError("fail")

    def get_m15_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200):
        raise MarketDataError("fail")

    def get_market_state(self) -> str:
        return "neutral"

    def get_sector_state(self, symbol: str) -> str:
        return "neutral"


class FallbackProviderTest(unittest.TestCase):
    def test_uses_cached_quote_when_primary_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileMarketDataCache(Path(tmp))
            provider = CachedFallbackMarketDataProvider(_PrimaryOk(), cache)
            quote = provider.get_latest_quote("002241")
            self.assertEqual(10.5, quote.price)

            provider = CachedFallbackMarketDataProvider(_PrimaryFail(), cache)
            cached_quote = provider.get_latest_quote("002241")
            self.assertEqual(10.5, cached_quote.price)
            self.assertTrue(provider.consume_notices())

    def test_prefers_fresh_cached_bars_before_primary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileMarketDataCache(Path(tmp))
            provider = CachedFallbackMarketDataProvider(_PrimaryOk(), cache)
            provider.get_m15_bars("002241", limit=1)
            provider.consume_notices()

            provider = CachedFallbackMarketDataProvider(_PrimaryFail(), cache)
            bars = provider.get_m15_bars("002241", limit=1)
            self.assertEqual(1, len(bars))
            self.assertTrue(any("已命中本地缓存15分钟数据" in item for item in provider.consume_notices()))

    def test_uses_cached_historical_m15_when_primary_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileMarketDataCache(Path(tmp))
            cache.save_bars(
                "002241",
                "15m",
                [
                    Bar(datetime(2026, 5, 20, 14, 30, 0), 10.0, 10.4, 9.9, 10.2, 100),
                    Bar(datetime(2026, 5, 20, 15, 0, 0), 10.2, 10.6, 10.1, 10.5, 200),
                    Bar(datetime(2026, 5, 21, 9, 45, 0), 10.6, 10.8, 10.5, 10.7, 150),
                ],
            )
            provider = CachedFallbackMarketDataProvider(_PrimaryFail(), cache)
            bars = provider.get_m15_bars_until("002241", datetime(2026, 5, 20, 15, 0, 0), limit=10)
            self.assertEqual(2, len(bars))
            self.assertEqual(datetime(2026, 5, 20, 15, 0, 0), bars[-1].ts)
            self.assertTrue(any("历史15分钟数据" in item for item in provider.consume_notices()))

    def test_exports_daily_key_levels_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileMarketDataCache(Path(tmp))
            cache.save_daily_zone_bundle(
                symbol="002241",
                latest_daily_ts=datetime(2026, 5, 27),
                daily_trend="up",
                zones=[
                    PriceZone(
                        name="daily_sr_1",
                        timeframe="1d",
                        low=27.8,
                        high=28.6,
                        score=5,
                        level=ZoneLevel.A,
                        tags=["resistance", "daily_fvg"],
                        touches=3,
                    )
                ],
            )
            export_path = Path(tmp) / "key_levels" / "002241_daily_key_levels.md"
            self.assertTrue(export_path.exists())
            content = export_path.read_text(encoding="utf-8")
            self.assertIn("# 002241 日线关键价位", content)
            self.assertIn("| A | daily_sr_1 | 27.80 | 28.60 | 5 | resistance, daily_fvg | 3 |", content)
