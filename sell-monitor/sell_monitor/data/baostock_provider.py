from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.domain.models import Bar


class BaostockMarketDataProvider:
    def __init__(self) -> None:
        try:
            import baostock as bs  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on local environment
            raise RuntimeError("BaoStock provider requires the 'baostock' package to be installed.") from exc
        self.bs = bs
        self._logged_in = False

    def get_daily_bars(self, symbol: str, limit: int = 200) -> list[Bar]:
        normalized_symbol = _normalize_symbol(symbol)
        end_dt = datetime.now()
        rows = self._query_history_rows(
            symbol=normalized_symbol,
            fields="date,code,open,high,low,close,volume",
            start_date="1990-01-01",
            end_date=end_dt.strftime("%Y-%m-%d"),
            frequency="d",
        )
        return _bars_from_rows(rows, timestamp_key="date")[-limit:]

    def get_m15_bars(self, symbol: str, limit: int = 200) -> list[Bar]:
        normalized_symbol = _normalize_symbol(symbol)
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=max(900, int(limit / 16 * 3) + 90))
        rows = self._query_history_rows(
            symbol=normalized_symbol,
            fields="date,time,code,open,high,low,close,volume",
            start_date=start_dt.strftime("%Y-%m-%d"),
            end_date=end_dt.strftime("%Y-%m-%d"),
            frequency="15",
        )
        return _bars_from_rows(rows, timestamp_key="time")[-limit:]

    def get_daily_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200) -> list[Bar]:
        normalized_symbol = _normalize_symbol(symbol)
        rows = self._query_history_rows(
            symbol=normalized_symbol,
            fields="date,code,open,high,low,close,volume",
            start_date="1990-01-01",
            end_date=end_dt.strftime("%Y-%m-%d"),
            frequency="d",
        )
        return [bar for bar in _bars_from_rows(rows, timestamp_key="date") if bar.ts <= end_dt][-limit:]

    def get_m15_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200) -> list[Bar]:
        normalized_symbol = _normalize_symbol(symbol)
        start_dt = end_dt - timedelta(days=max(900, int(limit / 16 * 3) + 90))
        rows = self._query_history_rows(
            symbol=normalized_symbol,
            fields="date,time,code,open,high,low,close,volume",
            start_date=start_dt.strftime("%Y-%m-%d"),
            end_date=end_dt.strftime("%Y-%m-%d"),
            frequency="15",
        )
        bars = [bar for bar in _bars_from_rows(rows, timestamp_key="time") if bar.ts <= end_dt]
        if bars:
            return bars[-limit:]
        raise MarketDataError(
            f"[{normalized_symbol}] BaoStock 历史15分钟数据为空，无法覆盖 {end_dt.strftime('%Y-%m-%d %H:%M:%S')}。"
        )

    def _query_history_rows(
        self,
        symbol: str,
        fields: str,
        start_date: str,
        end_date: str,
        frequency: str,
    ) -> list[dict[str, str]]:
        self._ensure_login()
        rs = self.bs.query_history_k_data_plus(
            _to_baostock_code(symbol),
            fields,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            adjustflag="2",
        )
        if getattr(rs, "error_code", "0") != "0":
            raise MarketDataError(f"[{symbol}] BaoStock 数据获取失败：{getattr(rs, 'error_msg', '')}")
        rows: list[dict[str, str]] = []
        fields_list = list(getattr(rs, "fields", []))
        while rs.next():
            values = rs.get_row_data()
            rows.append(dict(zip(fields_list, values)))
        if not rows:
            raise MarketDataError(f"[{symbol}] BaoStock 返回空数据")
        return rows

    def _ensure_login(self) -> None:
        if self._logged_in:
            return
        login_result = self.bs.login()
        if getattr(login_result, "error_code", "0") != "0":
            raise MarketDataError(f"BaoStock 登录失败：{getattr(login_result, 'error_msg', '')}")
        self._logged_in = True

    def close(self) -> None:
        if self._logged_in:
            self.bs.logout()
            self._logged_in = False


def _normalize_symbol(symbol: str) -> str:
    text = symbol.upper().strip()
    if "." in text:
        text = text.split(".", 1)[0]
    return text.zfill(6) if text.isdigit() else text


def _to_baostock_code(symbol: str) -> str:
    if symbol.startswith(("60", "68")):
        return f"sh.{symbol}"
    if symbol.startswith(("00", "30")):
        return f"sz.{symbol}"
    if symbol.startswith(("8", "4")):
        return f"bj.{symbol}"
    return symbol


def _bars_from_rows(rows: list[dict[str, str]], timestamp_key: str) -> list[Bar]:
    bars = [
        Bar(
            ts=_parse_timestamp(row.get(timestamp_key) or row.get("date")),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"] or 0),
        )
        for row in rows
        if _has_ohlcv(row)
    ]
    if not bars:
        raise MarketDataError("BaoStock 返回数据缺少有效 OHLCV。")
    return sorted(bars, key=lambda bar: bar.ts)


def _has_ohlcv(row: dict[str, str]) -> bool:
    return all(str(row.get(key, "")).strip() for key in ("open", "high", "low", "close"))


def _parse_timestamp(value: Any) -> datetime:
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y%m%d%H%M%S%f",
        "%Y%m%d%H%M%S",
        "%Y%m%d",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(text)
