from __future__ import annotations

from sell_monitor.domain.models import Bar, PriceZone, Signal


def detect_breakout_failure(bars: list[Bar], zone: PriceZone) -> Signal | None:
    recent = bars[-3:]
    pierced = any(bar.high > zone.high for bar in recent)
    back_below = recent[-1].close < zone.low
    if pierced and back_below:
        return Signal("breakout_failure", 2, True, "关键价位上冲后重新跌回区域下方，属于突破失败")
    return None

