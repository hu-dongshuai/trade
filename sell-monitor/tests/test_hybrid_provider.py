from __future__ import annotations

import unittest
from datetime import datetime

from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.data.hybrid_provider import HybridMarketDataProvider
from sell_monitor.domain.models import Bar, Quote


class _LiveProvider:
    def get_latest_quote(self, symbol: str):
        return Quote(symbol, 10.0, datetime(2026, 5, 28, 10, 0))

    def get_m15_bars(self, symbol: str, limit: int = 200):
        return [Bar(datetime(2026, 5, 28, 10, 0), 9.8, 10.2, 9.7, 10.0, 1000)]

    def get_market_state(self):
        return "neutral"

    def get_sector_state(self, symbol: str):
        return "neutral"


class _HistoryProvider:
    def get_m15_bars(self, symbol: str, limit: int = 200):
        return [Bar(datetime(2026, 5, 20, 10, 0), 8.8, 9.2, 8.7, 9.0, 1000)]


class _FailingHistoryProvider:
    def get_m15_bars(self, symbol: str, limit: int = 200):
        raise MarketDataError("history fail")


class HybridProviderTest(unittest.TestCase):
    def test_uses_live_provider_for_quote(self) -> None:
        provider = HybridMarketDataProvider(_LiveProvider(), _HistoryProvider())

        quote = provider.get_latest_quote("002241")

        self.assertEqual(10.0, quote.price)

    def test_prefers_history_provider_for_bars(self) -> None:
        provider = HybridMarketDataProvider(_LiveProvider(), _HistoryProvider())

        bars = provider.get_m15_bars("002241", limit=1)

        self.assertEqual(datetime(2026, 5, 20, 10, 0), bars[0].ts)

    def test_falls_back_to_live_provider_when_history_fails(self) -> None:
        provider = HybridMarketDataProvider(_LiveProvider(), _FailingHistoryProvider())

        bars = provider.get_m15_bars("002241", limit=1)

        self.assertEqual(datetime(2026, 5, 28, 10, 0), bars[0].ts)


if __name__ == "__main__":
    unittest.main()
