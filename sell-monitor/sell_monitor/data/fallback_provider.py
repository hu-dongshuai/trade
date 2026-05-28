from __future__ import annotations

from datetime import datetime

from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.data.cache_service import FileMarketDataCache


class CachedFallbackMarketDataProvider:
    QUOTE_TTL_SECONDS = 120
    M15_TTL_SECONDS = 300
    DAILY_TTL_SECONDS = 4 * 60 * 60
    STATE_TTL_SECONDS = 600

    def __init__(self, primary_provider, cache: FileMarketDataCache) -> None:
        self.primary_provider = primary_provider
        self.cache = cache
        self._notices: list[str] = []

    def consume_notices(self) -> list[str]:
        notices = list(self._notices)
        self._notices.clear()
        return notices

    def get_latest_quote(self, symbol: str):
        cached = self.cache.load_quote(symbol, max_age_seconds=self.QUOTE_TTL_SECONDS)
        if cached:
            self._notices.append(
                f"[{symbol}] 已命中本地缓存报价（时间 {cached.ts.strftime('%Y-%m-%d %H:%M:%S')}）"
            )
            return cached
        try:
            quote = self.primary_provider.get_latest_quote(symbol)
            self.cache.save_quote(quote)
            return quote
        except MarketDataError:
            cached = self.cache.load_quote(symbol)
            if cached:
                self._notices.append(
                    f"[{symbol}] 实时行情不可用，已回退到本地缓存报价（时间 {cached.ts.strftime('%Y-%m-%d %H:%M:%S')}）"
                )
                return cached
            raise

    def get_daily_bars(self, symbol: str, limit: int = 200):
        cached = self.cache.load_bars(symbol, "1d", max_age_seconds=self.DAILY_TTL_SECONDS)
        if cached:
            self._notices.append(f"[{symbol}] 已命中本地缓存日线数据")
            return cached[-limit:]
        try:
            bars = self.primary_provider.get_daily_bars(symbol, limit=limit)
            self.cache.save_bars(symbol, "1d", bars)
            return bars
        except MarketDataError:
            cached = self.cache.load_bars(symbol, "1d")
            if cached:
                self._notices.append(f"[{symbol}] 日线数据不可用，已回退到本地缓存日线数据")
                return cached[-limit:]
            raise

    def get_m15_bars(self, symbol: str, limit: int = 200):
        cached = self.cache.load_bars(symbol, "15m", max_age_seconds=self.M15_TTL_SECONDS)
        if cached:
            self._notices.append(f"[{symbol}] 已命中本地缓存15分钟数据")
            return cached[-limit:]
        try:
            bars = self.primary_provider.get_m15_bars(symbol, limit=limit)
            self.cache.save_bars(symbol, "15m", bars)
            return bars
        except MarketDataError:
            cached = self.cache.load_bars(symbol, "15m")
            if cached:
                self._notices.append(f"[{symbol}] 15分钟数据不可用，已回退到本地缓存15分钟数据")
                return cached[-limit:]
            raise

    def get_daily_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200):
        cached = self.cache.load_bars(symbol, "1d")
        cached_filtered = self._filter_bars_until(cached, end_dt, limit)
        if cached_filtered and self._bars_cover_datetime(cached, end_dt):
            self._notices.append(
                f"[{symbol}] 已命中本地缓存历史日线数据（截至 {end_dt.strftime('%Y-%m-%d %H:%M:%S')}）"
            )
            return cached_filtered

        try:
            if hasattr(self.primary_provider, "get_daily_bars_until"):
                bars = self.primary_provider.get_daily_bars_until(symbol, end_dt, limit=limit)
            else:
                bars = self._filter_bars_until(self.primary_provider.get_daily_bars(symbol, limit=1000), end_dt, limit)
            if bars:
                self.cache.save_bars(symbol, "1d", bars)
            return bars
        except MarketDataError as exc:
            if cached_filtered:
                self._notices.append(
                    f"[{symbol}] 历史日线数据不可用，已回退到本地缓存（截至 {end_dt.strftime('%Y-%m-%d %H:%M:%S')}）"
                )
                return cached_filtered
            raise exc

    def get_m15_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200):
        cached = self.cache.load_bars(symbol, "15m")
        cached_filtered = self._filter_bars_until(cached, end_dt, limit)
        if cached_filtered and self._bars_cover_datetime(cached, end_dt):
            self._notices.append(
                f"[{symbol}] 已命中本地缓存历史15分钟数据（截至 {end_dt.strftime('%Y-%m-%d %H:%M:%S')}）"
            )
            return cached_filtered

        try:
            if hasattr(self.primary_provider, "get_m15_bars_until"):
                bars = self.primary_provider.get_m15_bars_until(symbol, end_dt, limit=limit)
            else:
                bars = self._filter_bars_until(self.primary_provider.get_m15_bars(symbol, limit=1000), end_dt, limit)
            if bars:
                self.cache.save_bars(symbol, "15m", bars)
            return bars
        except MarketDataError as exc:
            if cached_filtered:
                self._notices.append(
                    f"[{symbol}] 历史15分钟数据不可用，已回退到本地缓存（截至 {end_dt.strftime('%Y-%m-%d %H:%M:%S')}）"
                )
                return cached_filtered
            raise exc

    def get_market_state(self) -> str:
        cached = self.cache.load_state("market_state", max_age_seconds=self.STATE_TTL_SECONDS)
        if cached:
            return cached
        value = self.primary_provider.get_market_state()
        self.cache.save_state("market_state", value)
        return value

    def get_sector_state(self, symbol: str) -> str:
        key = f"sector_state_{symbol}"
        cached = self.cache.load_state(key, max_age_seconds=self.STATE_TTL_SECONDS)
        if cached:
            return cached
        value = self.primary_provider.get_sector_state(symbol)
        self.cache.save_state(key, value)
        return value

    @staticmethod
    def _filter_bars_until(bars, end_dt: datetime, limit: int):
        if not bars:
            return []
        filtered = [bar for bar in bars if bar.ts <= end_dt]
        return filtered[-limit:]

    @staticmethod
    def _bars_cover_datetime(bars, end_dt: datetime) -> bool:
        return bool(bars) and bars[-1].ts >= end_dt
