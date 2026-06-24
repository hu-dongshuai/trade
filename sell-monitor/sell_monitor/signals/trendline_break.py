from __future__ import annotations

from sell_monitor.domain.models import Bar, Signal
from sell_monitor.indicators.swing_points import find_swing_lows


def detect_trendline_break(bars: list[Bar]) -> Signal | None:
    swings = find_swing_lows(bars)
    if len(swings) < 3:
        return None
    last_three = swings[-3:]
    lows = [bar.low for _, bar in last_three]
    if not (lows[0] < lows[1] < lows[2]):
        return None
    if bars[-1].close < lows[2] and bars[-2].close < lows[2]:
        return Signal(
            "trendline_break",
            2,
            True,
            "15分钟上升趋势线跌破且未快速收回",
            triggered_at=bars[-1].ts,
            trigger_price=bars[-1].close,
        )
    return None
