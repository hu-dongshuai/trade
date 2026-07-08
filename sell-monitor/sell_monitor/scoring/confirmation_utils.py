from __future__ import annotations

from sell_monitor.domain.models import Signal


EXIT_CONFIRMATION_GROUPS = {
    "structure": {"breakout_failure", "structure_break"},
    "trendline": {"trendline_break"},
    "momentum": {"m15_ma20_high_volume_break", "high_volume_drop_below_ma5"},
    "exhaustion": {"resistance_liquidity_grab"},
    "higher_tf": {"m60_bearish_confirmation"},
    "next_day": {"next_day_tail_break_confirmation"},
}

THIRD_WICK_CONFIRMATION_GROUPS = {
    "structure": {"breakout_failure", "structure_break"},
    "trendline": {"trendline_break"},
    "momentum": {"m15_ma20_high_volume_break", "high_volume_drop_below_ma5"},
    "higher_tf": {"m60_bearish_confirmation"},
    "next_day": {"next_day_tail_break_confirmation"},
}

TAIL_SENSITIVE_GROUPS = {"structure", "momentum", "higher_tf"}
TAIL_END_SIGNAL_NAMES = {
    "structure_break",
    "m15_ma20_high_volume_break",
    "m60_bearish_confirmation",
}


def confirmation_count(signals: list[Signal], groups: dict[str, set[str]]) -> int:
    grouped = _collect_grouped_signals(signals, groups)
    non_tail_count = 0
    tail_only_present = False

    for group_name, members in grouped.items():
        if group_name in TAIL_SENSITIVE_GROUPS and _all_tail_end_signals(members):
            tail_only_present = True
            continue
        non_tail_count += 1

    return non_tail_count + (1 if tail_only_present else 0)


def is_tail_cluster_waiting_next_day_confirmation(
    signals: list[Signal],
    groups: dict[str, set[str]],
) -> bool:
    grouped = _collect_grouped_signals(signals, groups)
    if "next_day" in grouped:
        return False

    tail_only_groups = [
        group_name
        for group_name, members in grouped.items()
        if group_name in TAIL_SENSITIVE_GROUPS and _all_tail_end_signals(members)
    ]
    non_tail_groups = [
        group_name
        for group_name, members in grouped.items()
        if not (group_name in TAIL_SENSITIVE_GROUPS and _all_tail_end_signals(members))
    ]
    return len(tail_only_groups) >= 2 and not non_tail_groups


def flat_confirmation_names(groups: dict[str, set[str]]) -> set[str]:
    merged: set[str] = set()
    for members in groups.values():
        merged.update(members)
    return merged


def _collect_grouped_signals(
    signals: list[Signal],
    groups: dict[str, set[str]],
) -> dict[str, list[Signal]]:
    grouped: dict[str, list[Signal]] = {}
    for signal in signals:
        if not signal.triggered:
            continue
        for group_name, members in groups.items():
            if signal.name in members:
                grouped.setdefault(group_name, []).append(signal)
    return grouped


def _all_tail_end_signals(signals: list[Signal]) -> bool:
    return bool(signals) and all(_is_tail_end_signal(signal) for signal in signals)


def _is_tail_end_signal(signal: Signal) -> bool:
    return (
        signal.name in TAIL_END_SIGNAL_NAMES
        and signal.triggered_at is not None
        and signal.triggered_at.hour == 15
        and signal.triggered_at.minute == 0
    )
