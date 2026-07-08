from __future__ import annotations

from dataclasses import replace

from sell_monitor.domain.enums import Action, Priority
from sell_monitor.domain.models import DailyContext, Decision


def cap_warning_state_action(decision: Decision, daily_context: DailyContext) -> Decision:
    if not daily_context.sell_warning_active or daily_context.active_zone is not None:
        return decision
    if decision.action != Action.EXIT_ALL:
        return decision
    reasons = list(decision.reasons)
    reasons.append("当前仅处于日线/60分钟转弱预警态，卖出动作上限为减仓")
    return replace(
        decision,
        action=Action.REDUCE,
        priority=Priority.HIGH,
        reasons=reasons,
        next_step="先减仓 50%；等待日线关键位或60分钟弱势继续确认后再评估清仓",
        cancel_condition="价格重新站回日线 MA20、60 分钟 MA20 并修复结构",
    )
