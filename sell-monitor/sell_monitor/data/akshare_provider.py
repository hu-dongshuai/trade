from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

from sell_monitor.domain.models import Bar, Quote


class MarketDataError(RuntimeError):
    pass


class AkshareMarketDataProvider:
    def __init__(self) -> None:
        try:
            import akshare as ak  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on local environment
            raise RuntimeError("AkShare provider requires the 'akshare' package to be installed.") from exc
        self.ak = ak

    def get_latest_quote(self, symbol: str) -> Quote:
        normalized_symbol = _normalize_symbol(symbol)
        errors: list[str] = []
        try:
            spot_df = _call_with_retry("stock_zh_a_spot_em", self.ak.stock_zh_a_spot_em)
            row = spot_df.loc[spot_df["代码"].astype(str) == normalized_symbol]
            if row.empty:
                raise MarketDataError(f"[{normalized_symbol}] 实时行情返回为空")
            latest = row.iloc[-1]
            return Quote(symbol=normalized_symbol, price=float(latest["最新价"]), ts=datetime.now())
        except Exception as exc:
            errors.append(f"实时行情接口失败: {exc}")
        try:
            fallback_bar = self.get_m15_bars(normalized_symbol, limit=1)[-1]
            return Quote(symbol=normalized_symbol, price=fallback_bar.close, ts=fallback_bar.ts)
        except Exception as exc:
            errors.append(f"15分钟行情回退失败: {exc}")
        try:
            fallback_bar = self.get_daily_bars(normalized_symbol, limit=1)[-1]
            return Quote(symbol=normalized_symbol, price=fallback_bar.close, ts=fallback_bar.ts)
        except Exception as exc:
            errors.append(f"日线收盘价回退失败: {exc}")
        raise MarketDataError(
            f"[{normalized_symbol}] 行情获取失败，AkShare/东方财富接口暂时不可用，请稍后重试。"
        ) from RuntimeError(" | ".join(errors))

    def get_daily_bars(self, symbol: str, limit: int = 200) -> list[Bar]:
        normalized_symbol = _normalize_symbol(symbol)
        end_date = datetime.now().strftime("%Y%m%d")
        try:
            daily_df = _call_with_retry(
                "stock_zh_a_hist",
                self.ak.stock_zh_a_hist,
                symbol=normalized_symbol,
                period="daily",
                start_date="19700101",
                end_date=end_date,
                adjust="qfq",
            )
            return _bars_from_dataframe(daily_df, limit=limit)
        except Exception:
            try:
                daily_df = _call_with_retry(
                    "stock_zh_a_daily",
                    self.ak.stock_zh_a_daily,
                    symbol=_to_sina_symbol(normalized_symbol),
                    adjust="qfq",
                )
                return _bars_from_dataframe(daily_df, limit=limit)
            except Exception as sina_exc:
                raise MarketDataError(f"[{normalized_symbol}] 日线数据获取失败，请稍后重试。") from sina_exc

    def get_m15_bars(self, symbol: str, limit: int = 200) -> list[Bar]:
        normalized_symbol = _normalize_symbol(symbol)
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=30)
        try:
            intraday_df = _call_with_retry(
                "stock_zh_a_hist_min_em",
                self.ak.stock_zh_a_hist_min_em,
                symbol=normalized_symbol,
                start_date=start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                end_date=end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                period="15",
                adjust="qfq",
            )
            return _bars_from_dataframe(intraday_df, limit=limit)
        except Exception:
            try:
                intraday_df = _call_with_retry(
                    "stock_zh_a_minute",
                    self.ak.stock_zh_a_minute,
                    symbol=_to_sina_symbol(normalized_symbol),
                    period="15",
                    adjust="qfq",
                )
                return _bars_from_dataframe(intraday_df, limit=limit)
            except Exception as sina_exc:
                raise MarketDataError(f"[{normalized_symbol}] 15分钟数据获取失败，请稍后重试。") from sina_exc

    def get_daily_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200) -> list[Bar]:
        normalized_symbol = _normalize_symbol(symbol)
        try:
            daily_df = _call_with_retry(
                "stock_zh_a_hist",
                self.ak.stock_zh_a_hist,
                symbol=normalized_symbol,
                period="daily",
                start_date="19700101",
                end_date=end_dt.strftime("%Y%m%d"),
                adjust="qfq",
            )
            return _bars_from_dataframe(daily_df, limit=limit)
        except Exception:
            try:
                daily_df = _call_with_retry(
                    "stock_zh_a_daily",
                    self.ak.stock_zh_a_daily,
                    symbol=_to_sina_symbol(normalized_symbol),
                    adjust="qfq",
                )
                bars = [bar for bar in _bars_from_dataframe(daily_df, limit=5000) if bar.ts <= end_dt]
                return bars[-limit:]
            except Exception as exc:
                raise MarketDataError(f"[{normalized_symbol}] 历史日线数据获取失败，请稍后重试。") from exc

    def get_m15_bars_until(self, symbol: str, end_dt: datetime, limit: int = 200) -> list[Bar]:
        normalized_symbol = _normalize_symbol(symbol)
        start_dt = end_dt - timedelta(days=45)
        try:
            intraday_df = _call_with_retry(
                "stock_zh_a_hist_min_em",
                self.ak.stock_zh_a_hist_min_em,
                symbol=normalized_symbol,
                start_date=start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                end_date=end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                period="15",
                adjust="qfq",
            )
            return _bars_from_dataframe(intraday_df, limit=limit)
        except Exception:
            try:
                intraday_df = _call_with_retry(
                    "stock_zh_a_minute",
                    self.ak.stock_zh_a_minute,
                    symbol=_to_sina_symbol(normalized_symbol),
                    period="15",
                    adjust="qfq",
                )
                bars = _bars_from_dataframe(intraday_df, limit=5000)
                return _filter_historical_m15_bars(normalized_symbol, bars, end_dt, limit)
            except MarketDataError:
                raise
            except Exception as exc:
                raise MarketDataError(f"[{normalized_symbol}] 历史15分钟数据获取失败，请稍后重试。") from exc

    def get_market_state(self) -> str:
        try:
            index_df = _call_with_retry("stock_zh_index_spot_em", self.ak.stock_zh_index_spot_em, symbol="沪深重要指数")
        except Exception:  # pragma: no cover - network/runtime dependent
            return "neutral"

        tracked_names = {"上证指数", "深证成指", "创业板指"}
        selected = index_df.loc[index_df["名称"].isin(tracked_names)]
        if selected.empty:
            return "neutral"

        up_count = 0
        down_count = 0
        for _, row in selected.iterrows():
            change_pct = float(row["涨跌幅"])
            if change_pct >= 0.5:
                up_count += 1
            elif change_pct <= -0.5:
                down_count += 1

        if down_count >= 2:
            return "down"
        if up_count >= 2:
            return "up"
        return "neutral"

    def get_sector_state(self, symbol: str) -> str:
        return "neutral"


def _normalize_symbol(symbol: str) -> str:
    text = symbol.upper().strip()
    if "." in text:
        text = text.split(".", 1)[0]
    return text


def _to_sina_symbol(symbol: str) -> str:
    if symbol.startswith(("60", "68")):
        return f"sh{symbol}"
    if symbol.startswith(("00", "30")):
        return f"sz{symbol}"
    if symbol.startswith("8"):
        return f"bj{symbol}"
    return symbol


def _call_with_retry(name: str, func, *args, **kwargs):
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            last_exc = exc
            if attempt == 2:
                break
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"{name} failed after 3 attempts") from last_exc


def _bars_from_dataframe(df: Any, limit: int) -> list[Bar]:
    if df is None or getattr(df, "empty", True):
        raise RuntimeError("AkShare returned empty bar data.")

    records = df.tail(limit).to_dict("records")
    bars: list[Bar] = []
    for item in records:
        bars.append(
            Bar(
                ts=_parse_timestamp(_pick(item, "时间", "日期", "date", "datetime", "day", "Day")),
                open=float(_pick(item, "开盘", "open", "Open")),
                high=float(_pick(item, "最高", "high", "High")),
                low=float(_pick(item, "最低", "low", "Low")),
                close=float(_pick(item, "收盘", "close", "Close")),
                volume=float(_pick(item, "成交量", "volume", "Volume")),
            )
        )
    return bars


def _pick(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item:
            return item[key]
    raise KeyError(f"Missing expected field. Tried keys: {keys}")


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(text)


def _filter_historical_m15_bars(symbol: str, bars: list[Bar], end_dt: datetime, limit: int) -> list[Bar]:
    filtered = [bar for bar in bars if bar.ts <= end_dt]
    if filtered:
        return filtered[-limit:]
    if bars:
        raise MarketDataError(
            f"[{symbol}] 已尝试拉取旧分钟数据，但当前可用在线15分钟数据最早仅到 "
            f"{bars[0].ts.strftime('%Y-%m-%d %H:%M:%S')}，无法覆盖 "
            f"{end_dt.strftime('%Y-%m-%d %H:%M:%S')}。"
        )
    raise MarketDataError(f"[{symbol}] 历史15分钟数据为空，请稍后重试。")
