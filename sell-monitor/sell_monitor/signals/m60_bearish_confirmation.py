from __future__ import annotations

from sell_monitor.domain.models import Bar, Signal
from sell_monitor.indicators.ma import closing_ma
from sell_monitor.indicators.timeframe import aggregate_m15_to_m60


def detect_m60_bearish_confirmation(m15_bars: list[Bar]) -> Signal | None:
    m60_bars = aggregate_m15_to_m60(m15_bars)
    if len(m60_bars) < 21:
        return None

    last = m60_bars[-1]
    prev = m60_bars[-2]
    ma20 = closing_ma(m60_bars, 20)
    if ma20 <= 0:
        return None

    lower_high = last.high < prev.high
    lower_low = last.low < prev.low
    below_ma20 = last.close <= ma20 * 0.997 and prev.close <= ma20
    close_breaks_prev_low = last.close < prev.low
    if lower_high and lower_low and below_ma20 and close_breaks_prev_low:
        return Signal(
            "m60_bearish_confirmation",
            2,
            True,
            f"{last.ts:%H:%M} 对应的60分钟K线确认转弱：低高点、低低点且收在 MA20 下方",
            triggered_at=last.ts,
            trigger_price=last.close,
        )
    return None
