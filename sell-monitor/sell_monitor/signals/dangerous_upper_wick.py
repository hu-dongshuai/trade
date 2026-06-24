from __future__ import annotations

from sell_monitor.domain.models import Bar, PriceZone, Signal
from sell_monitor.indicators.volume_stats import average_volume


def _is_dangerous_upper_wick(bar: Bar, avg_vol_10: float, zone: PriceZone) -> bool:
    if bar.body == 0 or bar.range == 0:
        return False
    ratio_ok = bar.upper_wick >= bar.body * 1.5
    shooting_star_ok = bar.upper_wick / bar.range >= 0.45
    touched_zone = (bar.high >= zone.low and bar.high <= zone.high * 1.02) or zone.contains(bar.high)
    volume_ok = avg_vol_10 > 0 and bar.volume >= avg_vol_10 * 1.5
    return (ratio_ok or shooting_star_ok) and touched_zone and volume_ok


def detect_dangerous_upper_wick_signals(bars: list[Bar], zone: PriceZone) -> list[Signal]:
    if len(bars) < 12:
        return []

    hits: list[int] = []
    for idx in range(10, len(bars)):
        avg_vol = average_volume(bars[max(0, idx - 10) : idx], 10)
        if _is_dangerous_upper_wick(bars[idx], avg_vol, zone):
            hits.append(idx)

    signals: list[Signal] = []
    if hits:
        first = bars[hits[0]]
        signals.append(
            Signal(
                "first_dangerous_upper_wick",
                1,
                True,
                f"15分钟出现第一根危险上影线（{first.ts:%H:%M}）",
                triggered_at=first.ts,
                trigger_price=first.close,
            )
        )
    if len(hits) >= 2 and hits[1] - hits[0] <= 16:
        second = bars[hits[1]]
        signals.append(
            Signal(
                "second_dangerous_upper_wick",
                2,
                True,
                f"16根K线内出现第二根危险上影线（{second.ts:%H:%M}）",
                triggered_at=second.ts,
                trigger_price=second.close,
            )
        )
    if len(hits) >= 3:
        third = bars[hits[2]]
        signals.append(
            Signal(
                "third_dangerous_upper_wick",
                3,
                True,
                f"出现第三根危险上影线（{third.ts:%H:%M}）",
                triggered_at=third.ts,
                trigger_price=third.close,
            )
        )
    return signals
