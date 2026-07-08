from __future__ import annotations

from sell_monitor.domain.enums import Action, Priority
from sell_monitor.domain.models import Decision, Position, Signal, UserRule
from sell_monitor.scoring.confirmation_utils import (
    THIRD_WICK_CONFIRMATION_GROUPS,
    confirmation_count,
    flat_confirmation_names,
    is_tail_cluster_waiting_next_day_confirmation,
)
from sell_monitor.scoring.score_engine import compute_score


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
        signal for signal in signals if signal.triggered and signal.name in flat_confirmation_names(THIRD_WICK_CONFIRMATION_GROUPS)
    ]
    confirmation_count = _third_wick_confirmation_count(signals)

    if confirmation_count >= 2:
        return Decision(
            symbol=symbol,
            action=Action.EXIT_ALL,
            total_score=actual_score,
            priority=Priority.IMMEDIATE,
            reasons=["出现第三根危险上影线"] + [signal.reason for signal in confirmation_signals],
            next_step="清仓；第三根危险上影线已获得两类破位确认",
            cancel_condition="价格快速收回 15 分钟 MA20 和关键价位上方，并确认是假破位",
            symbol_name=symbol_name,
            current_price=current_price,
        )

    if is_tail_cluster_waiting_next_day_confirmation(signals, THIRD_WICK_CONFIRMATION_GROUPS):
        return Decision(
            symbol=symbol,
            action=Action.REDUCE,
            total_score=actual_score,
            priority=Priority.HIGH,
            reasons=["出现第三根危险上影线"] + [signal.reason for signal in confirmation_signals] + ["15:00 尾盘共振破位先按减仓处理，等待次日首小时继续转弱再升级为清仓"],
            next_step="先减仓 50%；次日首小时若仍无法收复昨日尾盘破位位点并继续走弱，再执行清仓",
            cancel_condition="次日首小时重新收复昨日尾盘破位K线收盘价或重新站回 15 分钟 MA20 上方",
            symbol_name=symbol_name,
            current_price=current_price,
        )

    if confirmation_signals:
        return Decision(
            symbol=symbol,
            action=Action.REDUCE,
            total_score=actual_score,
            priority=Priority.HIGH,
            reasons=["出现第三根危险上影线"] + [signal.reason for signal in confirmation_signals] + ["清仓二次确认仍不足"],
            next_step="先减仓 50%；等待60分钟转弱、结构低点跌破或关键价位失守后再评估清仓",
            cancel_condition="价格继续站稳 15 分钟 MA20 和关键价位，且后续上影线信号消失",
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


def _third_wick_confirmation_count(signals: list[Signal]) -> int:
    return confirmation_count(signals, THIRD_WICK_CONFIRMATION_GROUPS)
