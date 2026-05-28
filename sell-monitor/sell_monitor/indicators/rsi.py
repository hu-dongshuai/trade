from __future__ import annotations

from statistics import mean

from sell_monitor.domain.models import Bar


def compute_rsi(bars: list[Bar], period: int = 14) -> float:
    if len(bars) <= period:
        return 50.0
    deltas = [curr.close - prev.close for prev, curr in zip(bars, bars[1:])]
    gains = [max(delta, 0.0) for delta in deltas]
    losses = [abs(min(delta, 0.0)) for delta in deltas]
    avg_gain = mean(gains[-period:])
    avg_loss = mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def has_bearish_rsi_divergence(bars: list[Bar], period: int = 14, lookback: int = 20) -> bool:
    if len(bars) < period + lookback:
        return False
    recent = bars[-lookback:]
    midpoint = len(recent) // 2
    first_half = recent[:midpoint]
    second_half = recent[midpoint:]
    first_high = max(first_half, key=lambda bar: bar.high)
    second_high = max(second_half, key=lambda bar: bar.high)
    if second_high.high <= first_high.high:
        return False
    first_idx = bars.index(first_high)
    second_idx = bars.index(second_high)
    rsi_first = compute_rsi(bars[: first_idx + 1], period)
    rsi_second = compute_rsi(bars[: second_idx + 1], period)
    return rsi_second < rsi_first

