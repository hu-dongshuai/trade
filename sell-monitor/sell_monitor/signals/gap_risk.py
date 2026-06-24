from __future__ import annotations

from sell_monitor.domain.models import Bar, Signal


def detect_gap_risk(daily_bars: list[Bar]) -> Signal | None:
    if len(daily_bars) < 4:
        return None
    recent = daily_bars[-4:]
    prev = recent[-2]
    current = recent[-1]
    if current.high < prev.low:
        return Signal(
            "gap_risk",
            2,
            True,
            "出现向下缺口且短期未回补",
            triggered_at=current.ts,
            trigger_price=current.close,
        )
    return None
