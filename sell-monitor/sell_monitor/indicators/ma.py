from __future__ import annotations

from statistics import mean

from sell_monitor.domain.models import Bar


def moving_average(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    window = values[-period:] if len(values) >= period else values
    return mean(window)


def closing_ma(bars: list[Bar], period: int) -> float:
    return moving_average([bar.close for bar in bars], period)

