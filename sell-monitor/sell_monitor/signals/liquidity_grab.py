from __future__ import annotations

from sell_monitor.domain.models import Bar, PriceZone, Signal
from sell_monitor.indicators.volume_stats import average_volume


def detect_resistance_liquidity_grab(bars: list[Bar], zone: PriceZone) -> Signal | None:
    if len(bars) < 12 or "resistance" not in zone.tags:
        return None
    recent_start = max(10, len(bars) - 3)
    for idx in range(recent_start, len(bars)):
        bar = bars[idx]
        avg_vol = average_volume(bars[idx - 10:idx], 10)
        swept_above_resistance = bar.high > zone.high
        failed_to_hold_breakout = bar.close < zone.high
        volume_confirms_sweep = avg_vol > 0 and bar.volume >= avg_vol * 1.2
        if swept_above_resistance and failed_to_hold_breakout and volume_confirms_sweep:
            return Signal(
                "resistance_liquidity_grab",
                3,
                True,
                "压力位上方扫流动性后回落（liquidity grab）",
            )
    return None
