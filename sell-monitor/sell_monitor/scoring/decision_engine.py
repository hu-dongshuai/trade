from __future__ import annotations

from sell_monitor.domain.enums import Action, Priority
from sell_monitor.domain.models import Decision, Signal


def build_decision(
    symbol: str,
    total_score: int,
    signals: list[Signal],
    symbol_name: str | None = None,
    current_price: float | None = None,
) -> Decision:
    reasons = [signal.reason for signal in signals if signal.triggered]

    if total_score > 5:
        return Decision(
            symbol=symbol,
            action=Action.EXIT_ALL,
            total_score=total_score,
            priority=Priority.IMMEDIATE,
            reasons=reasons,
            next_step="清仓卖出",
            cancel_condition="需要后续重新站回关键价位，并重建做多结构",
            symbol_name=symbol_name,
            current_price=current_price,
        )
    if total_score > 3:
        return Decision(
            symbol=symbol,
            action=Action.REDUCE,
            total_score=total_score,
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
        total_score=total_score,
        priority=Priority.NORMAL,
        reasons=reasons or ["未达到高质量卖出触发条件"],
        next_step="继续持有并监控",
        cancel_condition="若后续新增高质量卖出信号则重新评估",
        symbol_name=symbol_name,
        current_price=current_price,
    )
