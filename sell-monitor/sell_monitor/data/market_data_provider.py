from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Protocol

from sell_monitor.domain.models import Bar, FundamentalSnapshot, Quote
from sell_monitor.notifier.symbol_display import normalize_symbol_name


class MarketDataProvider(Protocol):
    def get_latest_quote(self, symbol: str) -> Quote: ...

    def get_daily_bars(self, symbol: str, limit: int = 200) -> list[Bar]: ...

    def get_m15_bars(self, symbol: str, limit: int = 200) -> list[Bar]: ...

    def get_daily_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200) -> list[Bar]: ...

    def get_m15_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200) -> list[Bar]: ...

    def get_market_state(self) -> str: ...

    def get_sector_state(self, symbol: str) -> str: ...

    def get_symbol_name(self, symbol: str) -> str: ...

    def get_fundamental_snapshot(self, symbol: str) -> FundamentalSnapshot | None: ...

    def get_fundamental_snapshot_until(self, symbol: str, end_dt: datetime) -> FundamentalSnapshot | None: ...


def _parse_bar(item: dict[str, object]) -> Bar:
    return Bar(
        ts=datetime.fromisoformat(str(item["ts"])),
        open=float(item["open"]),
        high=float(item["high"]),
        low=float(item["low"]),
        close=float(item["close"]),
        volume=float(item["volume"]),
    )


def _parse_optional_float(item: dict[str, object], key: str) -> float | None:
    value = item.get(key)
    if value is None or value == "":
        return None
    return float(value)


def _parse_fundamental(symbol: str, item: dict[str, object]) -> FundamentalSnapshot:
    report_date_raw = item.get("report_date")
    return FundamentalSnapshot(
        symbol=symbol,
        ts=datetime.fromisoformat(str(item.get("ts") or datetime.now().isoformat())),
        report_date=(datetime.fromisoformat(str(report_date_raw)) if report_date_raw else None),
        revenue_yoy=_parse_optional_float(item, "revenue_yoy"),
        previous_revenue_yoy=_parse_optional_float(item, "previous_revenue_yoy"),
        net_profit_yoy=_parse_optional_float(item, "net_profit_yoy"),
        deducted_net_profit_yoy=_parse_optional_float(item, "deducted_net_profit_yoy"),
        previous_deducted_net_profit_yoy=_parse_optional_float(item, "previous_deducted_net_profit_yoy"),
        gross_margin=_parse_optional_float(item, "gross_margin"),
        previous_gross_margin=_parse_optional_float(item, "previous_gross_margin"),
        net_margin=_parse_optional_float(item, "net_margin"),
        previous_net_margin=_parse_optional_float(item, "previous_net_margin"),
        roe=_parse_optional_float(item, "roe"),
        operating_cashflow_to_profit=_parse_optional_float(item, "operating_cashflow_to_profit"),
        debt_asset_ratio=_parse_optional_float(item, "debt_asset_ratio"),
        pe_percentile=_parse_optional_float(item, "pe_percentile"),
        event_risk=bool(item.get("event_risk", False)),
        event_note=(str(item["event_note"]) if item.get("event_note") else None),
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

    def get_symbol_name(self, symbol: str) -> str:
        payload = self._data["symbols"].get(symbol)
        if not payload:
            return symbol
        return normalize_symbol_name(symbol, str(payload.get("name", symbol))) or symbol

    def get_fundamental_snapshot(self, symbol: str) -> FundamentalSnapshot | None:
        payload = self._data["symbols"][symbol].get("fundamentals")
        if not payload:
            return None
        if isinstance(payload, list):
            payload = payload[-1]
        return _parse_fundamental(symbol, payload)

    def get_fundamental_snapshot_until(self, symbol: str, end_dt: datetime) -> FundamentalSnapshot | None:
        payload = self._data["symbols"][symbol].get("fundamentals")
        if not payload:
            return None
        if isinstance(payload, list):
            items = [item for item in payload if datetime.fromisoformat(str(item.get("report_date") or item["ts"])) <= end_dt]
            if not items:
                return None
            payload = items[-1]
        return _parse_fundamental(symbol, payload)
