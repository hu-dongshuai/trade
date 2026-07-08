from __future__ import annotations

from sell_monitor.domain.models import Bar, Signal
from sell_monitor.indicators.swing_points import find_swing_highs, find_swing_lows


STRUCTURE_BREAK_BUFFER_PCT = 0.003


def detect_structure_break(bars: list[Bar]) -> Signal | None:
    highs = find_swing_highs(bars)
    lows = find_swing_lows(bars)
    if not highs or not lows:
        return None
    last_high_idx, _ = highs[-1]
    prior_lows = [(idx, bar) for idx, bar in lows if idx < last_high_idx]
    if not prior_lows:
        return None
    structure_low = prior_lows[-1][1].low
    if bars[-1].close <= structure_low * (1 - STRUCTURE_BREAK_BUFFER_PCT):
        return Signal(
            "structure_break",
            2,
            True,
            "跌破最近一次创出新高后的回调低点",
            triggered_at=bars[-1].ts,
            trigger_price=bars[-1].close,
        )
    return None
