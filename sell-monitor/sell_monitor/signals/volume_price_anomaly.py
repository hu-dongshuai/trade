from __future__ import annotations

from sell_monitor.domain.models import Bar, Signal
from sell_monitor.indicators.ma import closing_ma
from sell_monitor.indicators.volume_stats import average_volume


def detect_volume_price_anomaly(m15_bars: list[Bar], daily_bars: list[Bar]) -> list[Signal]:
    signals: list[Signal] = []

    if len(m15_bars) >= 11:
        bar = m15_bars[-1]
        avg_volume_10 = average_volume(m15_bars[:-1], 10)
        if avg_volume_10 and bar.volume >= avg_volume_10 * 1.5 and bar.body <= bar.range * 0.35 and bar.upper_wick > 0:
            signals.append(
                Signal(
                    "volume_price_anomaly",
                    1,
                    True,
                    f"{bar.ts:%H:%M} 这根15分钟K线放量滞涨或量价异常",
                    triggered_at=bar.ts,
                    trigger_price=bar.close,
                )
            )

    if len(daily_bars) >= 6:
        current = daily_bars[-1]
        ma5 = closing_ma(daily_bars[:-1], 5)
        avg_daily_vol = average_volume(daily_bars[:-1], 10)
        if avg_daily_vol and current.volume >= avg_daily_vol * 2 and current.close < ma5:
            signals.append(
                Signal(
                    "high_volume_drop_below_ma5",
                    2,
                    True,
                    f"{current.ts:%Y-%m-%d} 这根日线放量大跌并跌破5日均线",
                    triggered_at=current.ts,
                    trigger_price=current.close,
                )
            )

    return signals
