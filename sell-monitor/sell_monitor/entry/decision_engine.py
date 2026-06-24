from __future__ import annotations

from sell_monitor.domain.enums import EntryAction
from sell_monitor.domain.models import EntryDecision
from sell_monitor.entry.models import EntryCandidate, EntryContext


ENTRY_ALLOW_THRESHOLD = 6


def build_entry_decision(context: EntryContext, candidates: list[EntryCandidate]) -> EntryDecision:
    if not candidates:
        return EntryDecision(
            symbol=context.symbol,
            symbol_name=context.symbol_name,
            action=EntryAction.REJECT_ENTRY,
            allowed=False,
            entry_score=0,
            entry_model="none",
            planned_entry_price=None,
            stop_loss_price=None,
            first_take_profit_price=None,
            risk_reward_ratio=None,
            reasons=["未识别出符合规则的回踩、订单块承接或真突破开仓模型"],
            blocking_reasons=["当前不满足明确开仓模型"],
            next_step="继续观察，等待回踩承接或真突破结构形成",
            current_price=context.current_price,
        )

    best = candidates[0]
    all_reasons = list(best.reasons)
    blocking_reasons = list(dict.fromkeys(best.blocking_reasons))
    hard_blocking_reasons = list(dict.fromkeys(best.hard_blocking_reasons))

    if context.market_state == "down":
        hard_blocking_reasons.append("大盘环境偏弱，开仓胜率下降")
    if context.sector_state == "weak":
        blocking_reasons.append("板块偏弱，不利于做多开仓")

    score = best.score
    if context.market_state == "down":
        score = max(0, score - 1)
    if context.sector_state == "weak":
        score = max(0, score - 1)

    missing_plan = (
        best.planned_entry_price is None
        or best.stop_loss_price is None
        or best.first_take_profit_price is None
        or best.risk_reward_ratio is None
    )
    if missing_plan:
        hard_blocking_reasons.append("止损位或第一止盈位无法明确识别")

    if best.risk_reward_ratio is not None and best.risk_reward_ratio < 2.0:
        hard_blocking_reasons.append("盈亏比低于 2:1")

    combined_blocking = list(dict.fromkeys(blocking_reasons + hard_blocking_reasons))
    allowed = score >= ENTRY_ALLOW_THRESHOLD and not missing_plan and not hard_blocking_reasons
    if allowed:
        action = EntryAction.ALLOW_ENTRY
        next_step = "按计划挂单价等待入场，并严格执行止损和第一止盈位"
    elif score >= max(ENTRY_ALLOW_THRESHOLD - 1, 1) and not hard_blocking_reasons:
        action = EntryAction.WATCH_ENTRY
        next_step = "模型接近成立，等待更清晰的小周期确认后再评估"
    else:
        action = EntryAction.REJECT_ENTRY
        next_step = "暂不允许开仓，等待趋势、位置或量价结构改善"

    return EntryDecision(
        symbol=context.symbol,
        symbol_name=context.symbol_name,
        action=action,
        allowed=allowed,
        entry_score=score,
        entry_model=best.model,
        planned_entry_price=best.planned_entry_price,
        stop_loss_price=best.stop_loss_price,
        first_take_profit_price=best.first_take_profit_price,
        risk_reward_ratio=best.risk_reward_ratio,
        reasons=all_reasons,
        blocking_reasons=combined_blocking,
        next_step=next_step,
        current_price=context.current_price,
    )
