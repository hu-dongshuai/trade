from __future__ import annotations

from sell_monitor.config import AppConfig
from sell_monitor.data.akshare_provider import AkshareMarketDataProvider
from sell_monitor.data.cache_service import FileMarketDataCache
from sell_monitor.data.fallback_provider import CachedFallbackMarketDataProvider
from sell_monitor.data.market_data_provider import StaticMarketDataProvider
from sell_monitor.data.miniqmt_provider import MiniQmtMarketDataProvider


def build_market_data_provider(config: AppConfig):
    if config.provider == "static":
        return StaticMarketDataProvider(config.market_data_path)
    if config.provider == "akshare":
        return CachedFallbackMarketDataProvider(
            primary_provider=AkshareMarketDataProvider(),
            cache=FileMarketDataCache(config.cache_dir),
        )
    if config.provider == "miniqmt":
        if not config.miniqmt:
            raise RuntimeError(
                "SELL_MONITOR_PROVIDER=miniqmt requires SELL_MONITOR_MINIQMT_USERDATA_PATH to be set."
            )
        return MiniQmtMarketDataProvider(config.miniqmt.userdata_path)
    raise RuntimeError(f"Unsupported provider: {config.provider}")
