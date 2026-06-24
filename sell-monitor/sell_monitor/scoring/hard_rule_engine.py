from __future__ import annotations

from sell_monitor.domain.enums import Action, Priority
from sell_monitor.domain.models import Decision, Position, Signal, UserRule
from sell_monitor.scoring.score_engine import compute_score


THIRD_WICK_CONFIRMATION_SIGNALS = {
    "breakout_failure",
    "trendline_break",
    "structure_break",
    "m15_ma20_high_volume_break",
    "high_volume_drop_below_ma5",
}


def evaluate_hard_rules(
    symbol: str,
    current_price: float,
    position: Position,
    rule: UserRule | None,
    signals: list[Signal],
    symbol_name: str | None = None,
) -> Decision | None:
    del position
    actual_score = compute_score(signals)

    if rule and rule.stop_loss is not None and current_price <= rule.stop_loss:
        return Decision(
            symbol=symbol,
            action=Action.STOP_LOSS,
            total_score=actual_score,
            priority=Priority.IMMEDIATE,
            reasons=[f"当前价格跌破预设止损位 {rule.stop_loss:.2f}"],
            next_step="立即执行止损卖出",
            cancel_condition="价格重新站回止损位上方，并确认是假跌破",
            symbol_name=symbol_name,
            current_price=current_price,
        )

    if rule and rule.hard_exit_note:
        return Decision(
            symbol=symbol,
            action=Action.EXIT_ALL,
            total_score=actual_score,
            priority=Priority.IMMEDIATE,
            reasons=[f"用户设置了硬性清仓规则：{rule.hard_exit_note}"],
            next_step="立即清仓",
            cancel_condition="仅在用户手动取消硬性清仓规则后撤销",
            symbol_name=symbol_name,
            current_price=current_price,
        )

    names = {signal.name for signal in signals if signal.triggered}
    if "third_dangerous_upper_wick" not in names:
        return None

    confirmation_signals = [
        signal for signal in signals if signal.triggered and signal.name in THIRD_WICK_CONFIRMATION_SIGNALS
    ]
    if confirmation_signals:
        return Decision(
            symbol=symbol,
            action=Action.EXIT_ALL,
            total_score=actual_score,
            priority=Priority.IMMEDIATE,
            reasons=["出现第三根危险上影线"] + [signal.reason for signal in confirmation_signals],
            next_step="清仓；第三根危险上影线已获得破位确认",
            cancel_condition="价格快速收回 15 分钟 MA20 和关键价位上方，并确认是假破位",
            symbol_name=symbol_name,
            current_price=current_price,
        )

    return Decision(
        symbol=symbol,
        action=Action.REDUCE,
        total_score=actual_score,
        priority=Priority.HIGH,
        reasons=["出现第三根危险上影线，但尚未出现破位确认"],
        next_step="先减仓 50%；等待跌破 15 分钟 MA20、结构低点或关键价位后再清仓",
        cancel_condition="价格继续站稳 15 分钟 MA20 和关键价位，且后续上影线信号消失",
        symbol_name=symbol_name,
        current_price=current_price,
    )
