from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Protocol

from sell_monitor.domain.models import Bar, Quote


class MarketDataProvider(Protocol):
    def get_latest_quote(self, symbol: str) -> Quote: ...

    def get_daily_bars(self, symbol: str, limit: int = 200) -> list[Bar]: ...

    def get_m15_bars(self, symbol: str, limit: int = 200) -> list[Bar]: ...

    def get_daily_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200) -> list[Bar]: ...

    def get_m15_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200) -> list[Bar]: ...

    def get_market_state(self) -> str: ...

    def get_sector_state(self, symbol: str) -> str: ...


def _parse_bar(item: dict[str, object]) -> Bar:
    return Bar(
        ts=datetime.fromisoformat(str(item["ts"])),
        open=float(item["open"]),
        high=float(item["high"]),
        low=float(item["low"]),
        close=float(item["close"]),
        volume=float(item["volume"]),
    )


class StaticMarketDataProvider:
    def __init__(self, path: Path) -> None:
        self._data = json.loads(path.read_text(encoding="utf-8"))

    def get_latest_quote(self, symbol: str) -> Quote:
        payload = self._data["symbols"][symbol]["quote"]
        return Quote(
            symbol=symbol,
            price=float(payload["price"]),
            ts=datetime.fromisoformat(payload["ts"]),
        )

    def get_daily_bars(self, symbol: str, limit: int = 200) -> list[Bar]:
        bars = self._data["symbols"][symbol]["daily_bars"][-limit:]
        return [_parse_bar(item) for item in bars]

    def get_m15_bars(self, symbol: str, limit: int = 200) -> list[Bar]:
        bars = self._data["symbols"][symbol]["m15_bars"][-limit:]
        return [_parse_bar(item) for item in bars]

    def get_daily_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200) -> list[Bar]:
        bars = [bar for bar in self.get_daily_bars(symbol, limit=5000) if bar.ts <= end_dt]
        return bars[-limit:]

    def get_m15_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200) -> list[Bar]:
        bars = [bar for bar in self.get_m15_bars(symbol, limit=5000) if bar.ts <= end_dt]
        return bars[-limit:]

    def get_market_state(self) -> str:
        return str(self._data["market"]["state"])

    def get_sector_state(self, symbol: str) -> str:
        return str(self._data["symbols"][symbol].get("sector_state", "neutral"))
