from __future__ import annotations

from sell_monitor.config import AppConfig
from sell_monitor.data.akshare_provider import AkshareMarketDataProvider
from sell_monitor.data.baostock_provider import BaostockMarketDataProvider
from sell_monitor.data.cache_service import FileMarketDataCache
from sell_monitor.data.fallback_provider import CachedFallbackMarketDataProvider
from sell_monitor.data.hybrid_provider import HybridMarketDataProvider
from sell_monitor.data.market_data_provider import StaticMarketDataProvider
from sell_monitor.data.miniqmt_provider import MiniQmtMarketDataProvider


def build_market_data_provider(config: AppConfig):
    if config.provider == "static":
        return StaticMarketDataProvider(config.market_data_path)
    if config.provider == "akshare":
        return CachedFallbackMarketDataProvider(
            primary_provider=_build_akshare_with_optional_baostock_history(),
            cache=FileMarketDataCache(config.cache_dir),
        )
    if config.provider == "baostock":
        return CachedFallbackMarketDataProvider(
            primary_provider=HybridMarketDataProvider(
                live_provider=AkshareMarketDataProvider(),
                history_provider=BaostockMarketDataProvider(),
            ),
            cache=FileMarketDataCache(config.cache_dir),
        )
    if config.provider == "miniqmt":
        if not config.miniqmt:
            raise RuntimeError(
                "SELL_MONITOR_PROVIDER=miniqmt requires SELL_MONITOR_MINIQMT_USERDATA_PATH to be set."
            )
        return MiniQmtMarketDataProvider(config.miniqmt.userdata_path)
    raise RuntimeError(f"Unsupported provider: {config.provider}")


def _build_akshare_with_optional_baostock_history():
    akshare_provider = AkshareMarketDataProvider()
    try:
        baostock_provider = BaostockMarketDataProvider()
    except RuntimeError:
        return akshare_provider
    return HybridMarketDataProvider(live_provider=akshare_provider, history_provider=baostock_provider)
