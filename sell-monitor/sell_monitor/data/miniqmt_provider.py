from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from sell_monitor.domain.models import Bar, Quote


def _format_symbol(symbol: str) -> str:
    if "." in symbol:
        return symbol
    if symbol.startswith(("60", "68")):
        return f"{symbol}.SH"
    if symbol.startswith(("00", "30")):
        return f"{symbol}.SZ"
    if symbol.startswith("8"):
        return f"{symbol}.BJ"
    raise ValueError(f"Unsupported symbol format: {symbol}")


class MiniQmtMarketDataProvider:
    def __init__(self, userdata_path: Path) -> None:
        try:
            from xtquant import xtdata  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on local broker environment
            raise RuntimeError(
                "MiniQMT provider requires xtquant. Install MiniQMT/XtQuant on this Windows machine first."
            ) from exc

        self.xtdata = xtdata
        self.userdata_path = userdata_path
        self.xtdata.data_dir = str(userdata_path)

    def get_latest_quote(self, symbol: str) -> Quote:
        stock_code = _format_symbol(symbol)
        tick = self.xtdata.get_full_tick([stock_code]).get(stock_code)
        if not tick:
            raise RuntimeError(f"MiniQMT returned no latest quote for {stock_code}")
        last_price = tick.get("lastPrice") or tick.get("last_price") or tick.get("close")
        last_time = tick.get("time")
        ts = datetime.fromtimestamp(last_time / 1000) if last_time else datetime.now()
        return Quote(symbol=symbol, price=float(last_price), ts=ts)

    def get_daily_bars(self, symbol: str, limit: int = 200) -> list[Bar]:
        return self._get_bars(symbol, period="1d", limit=limit)

    def get_m15_bars(self, symbol: str, limit: int = 200) -> list[Bar]:
        return self._get_bars(symbol, period="15m", limit=limit)

    def get_market_state(self) -> str:
        return "neutral"

    def get_sector_state(self, symbol: str) -> str:
        return "neutral"

    def _get_bars(self, symbol: str, period: str, limit: int) -> list[Bar]:
        stock_code = _format_symbol(symbol)
        self.xtdata.download_history_data(stock_code, period, incrementally=True)
        dataset = self.xtdata.get_market_data(
            field_list=["open", "high", "low", "close", "volume"],
            stock_list=[stock_code],
            period=period,
            count=limit,
            dividend_type="front_ratio",
            fill_data=True,
        )
        return _bars_from_xtdata(dataset, stock_code)


def _bars_from_xtdata(dataset: dict[str, Any], stock_code: str) -> list[Bar]:
    opens = _series_values(dataset, "open", stock_code)
    highs = _series_values(dataset, "high", stock_code)
    lows = _series_values(dataset, "low", stock_code)
    closes = _series_values(dataset, "close", stock_code)
    volumes = _series_values(dataset, "volume", stock_code)
    timestamps = _series_timestamps(dataset, "close")
    bars: list[Bar] = []
    for idx, ts_value in enumerate(timestamps):
        bars.append(
            Bar(
                ts=_parse_xt_timestamp(ts_value),
                open=float(opens[idx]),
                high=float(highs[idx]),
                low=float(lows[idx]),
                close=float(closes[idx]),
                volume=float(volumes[idx]),
            )
        )
    return bars


def _series_values(dataset: dict[str, Any], field: str, stock_code: str) -> list[Any]:
    frame = dataset[field]
    row = frame.loc[stock_code]
    return list(row.tolist() if hasattr(row, "tolist") else row)


def _series_timestamps(dataset: dict[str, Any], field: str) -> list[Any]:
    frame = dataset[field]
    columns = frame.columns
    return list(columns.tolist() if hasattr(columns, "tolist") else columns)


def _parse_xt_timestamp(value: Any) -> datetime:
    text = str(value)
    if text.isdigit():
        if len(text) == 8:
            return datetime.strptime(text, "%Y%m%d")
        if len(text) == 14:
            return datetime.strptime(text, "%Y%m%d%H%M%S")
        if len(text) == 13:
            return datetime.fromtimestamp(int(text) / 1000)
    return datetime.fromisoformat(text)
