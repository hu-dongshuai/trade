from __future__ import annotations

from sell_monitor.domain.enums import Action, Priority
from sell_monitor.domain.models import Decision, Signal


BACKGROUND_SIGNAL_NAMES = {
    "market_weakness",
    "a_level_zone",
    "sell_warning_state",
}

AUXILIARY_SIGNAL_NAMES = {
    "rsi_bearish_divergence",
    "volume_price_anomaly",
    "first_dangerous_upper_wick",
}

EXIT_CONFIRMATION_GROUPS = {
    "structure": {"breakout_failure", "structure_break"},
    "trendline": {"trendline_break"},
    "momentum": {"m15_ma20_high_volume_break", "high_volume_drop_below_ma5"},
    "exhaustion": {"resistance_liquidity_grab"},
    "higher_tf": {"m60_bearish_confirmation"},
}

REDUCE_CORE_THRESHOLD = 2
EXIT_CORE_THRESHOLD = 4
EXIT_CONFIRMATION_THRESHOLD = 2


def build_decision(
    symbol: str,
    total_score: int,
    signals: list[Signal],
    symbol_name: str | None = None,
    current_price: float | None = None,
) -> Decision:
    del total_score
    reasons = [signal.reason for signal in signals if signal.triggered]
    effective_score, core_score = _effective_sell_score(signals)

    if effective_score > 5 and core_score >= EXIT_CORE_THRESHOLD:
        if _exit_confirmation_count(signals) >= EXIT_CONFIRMATION_THRESHOLD:
            return Decision(
                symbol=symbol,
                action=Action.EXIT_ALL,
                total_score=effective_score,
                priority=Priority.IMMEDIATE,
                reasons=reasons,
                next_step="清仓卖出",
                cancel_condition="需要后续重新站回关键价位，并重建做多结构",
                symbol_name=symbol_name,
                current_price=current_price,
            )
        return Decision(
            symbol=symbol,
            action=Action.REDUCE,
            total_score=effective_score,
            priority=Priority.HIGH,
            reasons=reasons + ["清仓二次确认不足，先按减仓处理"],
            next_step="先减仓 50%；等待60分钟或关键破位继续确认后再评估清仓",
            cancel_condition="价格重新站稳 15 分钟 MA20、60 分钟 MA20 或关键价位上方",
            symbol_name=symbol_name,
            current_price=current_price,
        )
    if effective_score > 3 and core_score >= REDUCE_CORE_THRESHOLD:
        return Decision(
            symbol=symbol,
            action=Action.REDUCE,
            total_score=effective_score,
            priority=Priority.HIGH,
            reasons=reasons,
            next_step="减仓，优先减掉 50% 风险仓位",
            cancel_condition="价格重新站稳关键价位，且卖点信号消失",
            symbol_name=symbol_name,
            current_price=current_price,
        )
    return Decision(
        symbol=symbol,
        action=Action.HOLD,
        total_score=effective_score,
        priority=Priority.NORMAL,
        reasons=reasons or ["未达到高质量卖出触发条件"],
        next_step="继续持有并监控",
        cancel_condition="若后续新增高质量卖出信号则重新评估",
        symbol_name=symbol_name,
        current_price=current_price,
    )


def _effective_sell_score(signals: list[Signal]) -> tuple[int, int]:
    core_score = 0
    auxiliary_score = 0
    background_score = 0
    for signal in signals:
        if not signal.triggered:
            continue
        if signal.name in BACKGROUND_SIGNAL_NAMES:
            background_score += signal.score
        elif signal.name in AUXILIARY_SIGNAL_NAMES:
            auxiliary_score += signal.score
        else:
            core_score += signal.score
    effective_score = core_score + auxiliary_score + min(1, background_score)
    return effective_score, core_score


def _exit_confirmation_count(signals: list[Signal]) -> int:
    names = {signal.name for signal in signals if signal.triggered}
    return sum(1 for members in EXIT_CONFIRMATION_GROUPS.values() if names & members)
