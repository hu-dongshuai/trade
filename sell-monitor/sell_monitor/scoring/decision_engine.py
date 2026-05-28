from __future__ import annotations

from sell_monitor.domain.enums import Action, Priority
from sell_monitor.domain.models import Decision, Signal


def build_decision(symbol: str, total_score: int, signals: list[Signal]) -> Decision:
    reasons = [signal.reason for signal in signals if signal.triggered]
    if total_score > 5:
        return Decision(
            symbol=symbol,
            action=Action.EXIT_ALL,
            total_score=total_score,
            priority=Priority.IMMEDIATE,
            reasons=reasons,
            next_step="清仓卖出",
            cancel_condition="需要后续重新站回关键价位并重新建立做多结构",
        )
    if total_score > 3:
        return Decision(
            symbol=symbol,
            action=Action.REDUCE,
            total_score=total_score,
            priority=Priority.HIGH,
            reasons=reasons,
            next_step="减仓，优先减掉50%风险仓位",
            cancel_condition="价格重新站稳关键价位且卖点信号消失",
        )
    return Decision(
        symbol=symbol,
        action=Action.HOLD,
        total_score=total_score,
        priority=Priority.NORMAL,
        reasons=reasons or ["未达到高质量卖出触发条件"],
        next_step="继续持有并监控",
        cancel_condition="若后续新增高质量卖出信号则重新评估",
    )

