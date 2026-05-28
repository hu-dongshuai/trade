from __future__ import annotations

from statistics import mean

from sell_monitor.domain.models import Bar


def compute_atr(bars: list[Bar], period: int = 14) -> float:
    if len(bars) < 2:
        return 0.0
    trs: list[float] = []
    for prev, current in zip(bars, bars[1:]):
        tr = max(
            current.high - current.low,
            abs(current.high - prev.close),
            abs(current.low - prev.close),
        )
        trs.append(tr)
    window = trs[-period:] if len(trs) >= period else trs
    return mean(window) if window else 0.0

