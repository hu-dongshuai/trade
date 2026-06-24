from __future__ import annotations

from sell_monitor.domain.models import Bar, Signal
from sell_monitor.indicators.volume_stats import average_volume


def detect_open_20min_risk(m15_bars: list[Bar]) -> Signal | None:
    if len(m15_bars) < 12:
        return None

    session = m15_bars[-12:]
    first_two = session[:2]
    avg_volume = average_volume(session, 10)
    if first_two[-1].close < first_two[0].open and sum(bar.volume for bar in first_two) >= avg_volume * 1.5:
        return Signal(
            "open_20min_risk",
            2,
            True,
            f"{first_two[-1].ts:%H:%M} 这根15分钟K线确认开盘前20分钟放量杀跌且未收回",
            triggered_at=first_two[-1].ts,
            trigger_price=first_two[-1].close,
        )
    return None
