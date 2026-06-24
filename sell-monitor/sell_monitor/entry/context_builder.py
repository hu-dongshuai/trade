from __future__ import annotations

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import DailyContext
from sell_monitor.entry.models import EntryContext
from sell_monitor.indicators.ma import closing_ma


def build_entry_context(daily_context: DailyContext, symbol_name: str | None = None) -> EntryContext:
    daily_bars = daily_context.daily_bars
    ma20 = closing_ma(daily_bars, 20) if len(daily_bars) >= 20 else 0.0
    ma200 = closing_ma(daily_bars, 200) if len(daily_bars) >= 200 else ma20
    current_price = daily_context.current_price

    is_trend_healthy = (
        daily_context.daily_trend == "up"
        and current_price >= ma20
        and (ma200 <= 0 or current_price >= ma200)
    )
    m60_bars = _build_m60_bars(daily_context.daily_bars)
    m60_ma20 = closing_ma(m60_bars, 20) if len(m60_bars) >= 20 else 0.0
    is_m60_trend_healthy = len(m60_bars) >= 20 and m60_bars[-1].close >= m60_ma20 and _higher_highs_higher_lows(m60_bars[-6:])
    recent_5d_return = _window_return(daily_bars, 5)
    recent_10d_return = _window_return(daily_bars, 10)
    daily_relative_strength_ok = recent_5d_return >= 0 and recent_10d_return >= 3
    avg_daily_turnover = _avg_daily_turnover(daily_bars, 20)
    liquidity_ok = avg_daily_turnover >= 20_000_000

    daily_support_zones = [
        zone
        for zone in daily_context.daily_zones
        if "support" in zone.tags and zone.level in {ZoneLevel.A, ZoneLevel.B, ZoneLevel.C}
    ]
    daily_resistance_zones = [
        zone
        for zone in daily_context.daily_zones
        if "resistance" in zone.tags and zone.level in {ZoneLevel.A, ZoneLevel.B, ZoneLevel.C}
    ]

    return EntryContext(
        symbol=daily_context.symbol,
        symbol_name=symbol_name,
        current_price=current_price,
        market_state=daily_context.market_state,
        sector_state=daily_context.sector_state,
        daily_trend=daily_context.daily_trend,
        is_trend_healthy=is_trend_healthy,
        is_m60_trend_healthy=is_m60_trend_healthy,
        daily_relative_strength_ok=daily_relative_strength_ok,
        liquidity_ok=liquidity_ok,
        avg_daily_turnover=avg_daily_turnover,
        recent_5d_return=recent_5d_return,
        recent_10d_return=recent_10d_return,
        daily_support_zones=daily_support_zones,
        daily_resistance_zones=daily_resistance_zones,
    )


def _window_return(bars, size: int) -> float:
    if len(bars) < size + 1:
        return 0.0
    start = bars[-size - 1].close
    end = bars[-1].close
    if start <= 0:
        return 0.0
    return round((end - start) / start * 100, 2)


def _avg_daily_turnover(bars, size: int) -> float:
    if not bars:
        return 0.0
    sample = bars[-size:]
    return sum(bar.close * bar.volume for bar in sample) / len(sample)


def _higher_highs_higher_lows(bars) -> bool:
    if len(bars) < 4:
        return False
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    return highs[-1] >= max(highs[-3:-1]) and lows[-1] >= min(lows[-3:-1])


def _build_m60_bars(daily_bars):
    # Current project does not yet have dedicated 60m history in the entry context,
    # so we use grouped recent daily structure as a conservative proxy.
    return daily_bars
