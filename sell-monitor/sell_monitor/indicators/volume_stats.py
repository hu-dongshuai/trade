from __future__ import annotations

from statistics import mean

from sell_monitor.domain.models import Bar


def average_volume(bars: list[Bar], period: int) -> float:
    if not bars:
        return 0.0
    window = bars[-period:] if len(bars) >= period else bars
    return mean([bar.volume for bar in window])


def is_volume_surge(current_volume: float, avg_volume: float, multiplier: float = 1.5) -> bool:
    return avg_volume > 0 and current_volume >= avg_volume * multiplier

