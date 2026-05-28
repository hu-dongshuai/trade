from __future__ import annotations

from sell_monitor.domain.models import Signal


def compute_score(signals: list[Signal]) -> int:
    return sum(signal.score for signal in signals if signal.triggered)

