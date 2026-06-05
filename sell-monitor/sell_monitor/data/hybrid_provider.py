from __future__ import annotations

from datetime import datetime

from sell_monitor.data.akshare_provider import MarketDataError


class HybridMarketDataProvider:
    def __init__(self, live_provider, history_provider) -> None:
        self.live_provider = live_provider
        self.history_provider = history_provider

    def get_latest_quote(self, symbol: str):
        return self.live_provider.get_latest_quote(symbol)

    def get_daily_bars(self, symbol: str, limit: int = 200):
        return self._history_first("get_daily_bars", symbol, limit=limit)

    def get_m15_bars(self, symbol: str, limit: int = 200):
        return self._history_first("get_m15_bars", symbol, limit=limit)

    def get_daily_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200):
        return self._history_first("get_daily_bars_until", symbol, end_dt, limit=limit)

    def get_m15_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200):
        return self._history_first("get_m15_bars_until", symbol, end_dt, limit=limit)

    def get_market_state(self) -> str:
        return self.live_provider.get_market_state()

    def get_sector_state(self, symbol: str) -> str:
        return self.live_provider.get_sector_state(symbol)

    def get_symbol_name(self, symbol: str) -> str:
        method = getattr(self.live_provider, "get_symbol_name", None)
        if method is None:
            return symbol
        return method(symbol)

    def get_fundamental_snapshot(self, symbol: str):
        method = getattr(self.live_provider, "get_fundamental_snapshot", None)
        if method is None:
            return None
        return method(symbol)

    def get_fundamental_snapshot_until(self, symbol: str, end_dt: datetime):
        method = getattr(self.live_provider, "get_fundamental_snapshot_until", None)
        if method is None:
            return None
        return method(symbol, end_dt)

    def _history_first(self, method_name: str, *args, **kwargs):
        errors: list[str] = []
        for provider in (self.history_provider, self.live_provider):
            method = getattr(provider, method_name, None)
            if method is None:
                continue
            try:
                return method(*args, **kwargs)
            except MarketDataError as exc:
                errors.append(str(exc))
            except Exception as exc:
                errors.append(f"{provider.__class__.__name__}.{method_name} 失败：{exc}")
        symbol = args[0] if args else "unknown"
        raise MarketDataError(f"[{symbol}] 所有网络数据源均获取失败：{' | '.join(errors)}")

    def close(self) -> None:
        for provider in (self.history_provider, self.live_provider):
            close = getattr(provider, "close", None)
            if callable(close):
                close()
