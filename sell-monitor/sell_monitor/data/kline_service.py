from __future__ import annotations

from sell_monitor.data.market_data_provider import MarketDataProvider
from sell_monitor.domain.models import Bar


class KlineService:
    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    def get_daily(self, symbol: str, limit: int = 200) -> list[Bar]:
        return self.provider.get_daily_bars(symbol, limit=limit)

    def get_m15(self, symbol: str, limit: int = 200) -> list[Bar]:
        return self.provider.get_m15_bars(symbol, limit=limit)

