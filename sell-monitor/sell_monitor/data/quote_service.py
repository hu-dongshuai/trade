from __future__ import annotations

from sell_monitor.data.market_data_provider import MarketDataProvider
from sell_monitor.domain.models import Quote


class QuoteService:
    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    def get_latest_quote(self, symbol: str) -> Quote:
        return self.provider.get_latest_quote(symbol)

