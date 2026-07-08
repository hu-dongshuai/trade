from __future__ import annotations

from sell_monitor.domain.models import Bar


def aggregate_m15_to_m60(bars: list[Bar]) -> list[Bar]:
    grouped: list[Bar] = []
    current_day = None
    bucket: list[Bar] = []

    for bar in bars:
        bar_day = bar.ts.date()
        if current_day != bar_day:
            bucket = []
            current_day = bar_day
        bucket.append(bar)
        if len(bucket) == 4:
            grouped.append(
                Bar(
                    ts=bucket[-1].ts,
                    open=bucket[0].open,
                    high=max(item.high for item in bucket),
                    low=min(item.low for item in bucket),
                    close=bucket[-1].close,
                    volume=sum(item.volume for item in bucket),
                )
            )
            bucket = []

    return grouped
