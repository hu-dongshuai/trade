from __future__ import annotations

from sell_monitor.domain.models import Bar


def find_swing_highs(bars: list[Bar], left: int = 2, right: int = 2) -> list[tuple[int, Bar]]:
    result: list[tuple[int, Bar]] = []
    for idx in range(left, len(bars) - right):
        center = bars[idx]
        if all(center.high > bars[i].high for i in range(idx - left, idx)) and all(
            center.high >= bars[i].high for i in range(idx + 1, idx + right + 1)
        ):
            result.append((idx, center))
    return result


def find_swing_lows(bars: list[Bar], left: int = 2, right: int = 2) -> list[tuple[int, Bar]]:
    result: list[tuple[int, Bar]] = []
    for idx in range(left, len(bars) - right):
        center = bars[idx]
        if all(center.low < bars[i].low for i in range(idx - left, idx)) and all(
            center.low <= bars[i].low for i in range(idx + 1, idx + right + 1)
        ):
            result.append((idx, center))
    return result

