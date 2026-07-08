from __future__ import annotations

from sell_monitor.domain.enums import EntryAction, ZoneLevel
from sell_monitor.domain.models import EntryDecision, PriceZone
from sell_monitor.entry.models import EntryCandidate, EntryContext


STANDARD_ALLOW_THRESHOLD = 5
STANDARD_WATCH_THRESHOLD = 5
STANDARD_MIN_RR = 1.5

PROBE_ENTRY_ALLOW_THRESHOLD = 4
PROBE_ENTRY_MIN_RR = 1.5

T_REENTRY_ALLOW_THRESHOLD = 5
T_REENTRY_WATCH_THRESHOLD = 4
T_REENTRY_MIN_RR = 1.5

ROUTE_STANDARD = "standard_entry"
ROUTE_PROBE = "probe_entry"
ROUTE_T_REENTRY = "t_reentry"
ROUTE_REJECT = "reject_reentry"

PROBE_ENTRY_SUPPORTED_MODELS = {"pullback_buy", "order_block_buy"}
T_REENTRY_SUPPORTED_MODELS = {"pullback_buy", "order_block_buy"}
PROBE_ENTRY_RELAXABLE_BLOCK_MARKERS = (
    "15分钟尚未出现明确承接确认",
    "小周期未给出明确承接确认",
    "上方压力过近",
)
T_REENTRY_RELAXABLE_BLOCK_MARKERS = (
    "15分钟尚未出现明确承接确认",
    "小周期未给出明确承接确认",
    "第一止盈位空间不足",
    "上方压力过近",
    "标准开仓要求盈亏比至少 1.5:1",
)


def build_entry_decision(context: EntryContext, candidates: list[EntryCandidate]) -> EntryDecision:
    if not candidates:
        return EntryDecision(
            symbol=context.symbol,
            symbol_name=context.symbol_name,
            action=EntryAction.REJECT_ENTRY,
            allowed=False,
            entry_score=0,
            entry_route=ROUTE_REJECT,
            entry_model="none",
            planned_entry_price=None,
            stop_loss_price=None,
            first_take_profit_price=None,
            risk_reward_ratio=None,
            reasons=["未识别出符合规则的回踩、订单块承接或真突破开仓模型。"],
            blocking_reasons=["当前不满足标准开仓，也不满足做T回补的基础条件。"],
            next_step="继续观察，等待回踩承接、订单块低吸或真突破结构出现。",
            current_price=context.current_price,
        )

    best = candidates[0]
    base_reasons = list(best.reasons)
    blocking_reasons = list(dict.fromkeys(best.blocking_reasons))
    hard_blocking_reasons = list(dict.fromkeys(best.hard_blocking_reasons))

    score = best.score
    if context.market_state == "down":
        hard_blocking_reasons.append("大盘环境转弱，开仓胜率明显下降。")
        score = max(0, score - 1)
    if context.sector_state == "weak":
        blocking_reasons.append("板块偏弱，做多延续性需要打折。")
        score = max(0, score - 1)

    missing_plan = (
        best.planned_entry_price is None
        or best.stop_loss_price is None
        or best.first_take_profit_price is None
        or best.risk_reward_ratio is None
    )
    if missing_plan:
        hard_blocking_reasons.append("止损位或第一止盈位无法明确识别。")

    if best.risk_reward_ratio is not None and best.risk_reward_ratio < STANDARD_MIN_RR:
        hard_blocking_reasons.append("标准开仓要求盈亏比至少 1.5:1。")

    combined_blocking = list(dict.fromkeys(blocking_reasons + hard_blocking_reasons))
    standard_allowed = score >= STANDARD_ALLOW_THRESHOLD and not missing_plan and not hard_blocking_reasons
    if standard_allowed:
        return EntryDecision(
            symbol=context.symbol,
            symbol_name=context.symbol_name,
            action=EntryAction.ALLOW_ENTRY,
            allowed=True,
            entry_score=score,
            entry_route=ROUTE_STANDARD,
            entry_model=best.model,
            planned_entry_price=best.planned_entry_price,
            stop_loss_price=best.stop_loss_price,
            first_take_profit_price=best.first_take_profit_price,
            risk_reward_ratio=best.risk_reward_ratio,
            reasons=base_reasons,
            blocking_reasons=combined_blocking,
            next_step="按标准开仓计划执行，挂单后严格遵守止损与第一止盈位。",
            current_price=context.current_price,
        )

    t_eval = _evaluate_t_reentry(context, best, score, missing_plan)
    if t_eval["allowed"]:
        reasons = list(dict.fromkeys(base_reasons + t_eval["reasons"]))
        blocks = list(dict.fromkeys(combined_blocking + t_eval["warnings"]))
        return EntryDecision(
            symbol=context.symbol,
            symbol_name=context.symbol_name,
            action=EntryAction.ALLOW_ENTRY,
            allowed=True,
            entry_score=t_eval["score"],
            entry_route=ROUTE_T_REENTRY,
            entry_model=best.model,
            planned_entry_price=best.planned_entry_price,
            stop_loss_price=best.stop_loss_price,
            first_take_profit_price=best.first_take_profit_price,
            risk_reward_ratio=best.risk_reward_ratio,
            reasons=reasons,
            blocking_reasons=blocks,
            next_step="按 T 仓回补执行，只回补计划中的 T 仓，不扩张主仓；跌破止损位立即撤退。",
            current_price=context.current_price,
        )

    probe_eval = _evaluate_probe_entry(context, best, score, missing_plan)
    if probe_eval["allowed"]:
        reasons = list(dict.fromkeys(base_reasons + probe_eval["reasons"]))
        blocks = list(dict.fromkeys(combined_blocking + probe_eval["warnings"]))
        return EntryDecision(
            symbol=context.symbol,
            symbol_name=context.symbol_name,
            action=EntryAction.ALLOW_ENTRY,
            allowed=True,
            entry_score=probe_eval["score"],
            entry_route=ROUTE_PROBE,
            entry_model=best.model,
            planned_entry_price=best.planned_entry_price,
            stop_loss_price=best.stop_loss_price,
            first_take_profit_price=best.first_take_profit_price,
            risk_reward_ratio=best.risk_reward_ratio,
            reasons=reasons,
            blocking_reasons=blocks,
            next_step="允许轻仓试错开仓，只使用计划仓位的 1/3 到 1/2；若15分钟再次转弱或跌破止损位，立即撤退。",
            current_price=context.current_price,
        )

    if score >= STANDARD_WATCH_THRESHOLD and not hard_blocking_reasons:
        action = EntryAction.WATCH_ENTRY
        route = ROUTE_STANDARD
        next_step = "接近标准开仓，但还缺一层确认；等待更清晰的 15 分钟承接后再评估。"
        watch_score = score
    elif t_eval["watch"]:
        action = EntryAction.WATCH_ENTRY
        route = ROUTE_T_REENTRY
        next_step = "暂时只列入 T 仓回补观察，等价格更贴近支撑区或出现更干净的 15 分钟承接后再评估。"
        watch_score = t_eval["score"]
        combined_blocking = list(dict.fromkeys(combined_blocking + t_eval["warnings"] + t_eval["blocking"]))
    else:
        action = EntryAction.REJECT_ENTRY
        route = ROUTE_REJECT
        next_step = "暂不允许开仓或回补，等待趋势、位置、量价结构和盈亏比同步改善。"
        watch_score = score
        combined_blocking = list(dict.fromkeys(combined_blocking + t_eval["warnings"] + t_eval["blocking"]))

    return EntryDecision(
        symbol=context.symbol,
        symbol_name=context.symbol_name,
        action=action,
        allowed=False,
        entry_score=watch_score,
        entry_route=route,
        entry_model=best.model,
        planned_entry_price=best.planned_entry_price,
        stop_loss_price=best.stop_loss_price,
        first_take_profit_price=best.first_take_profit_price,
        risk_reward_ratio=best.risk_reward_ratio,
        reasons=base_reasons,
        blocking_reasons=combined_blocking,
        next_step=next_step,
        current_price=context.current_price,
    )


def _evaluate_probe_entry(
    context: EntryContext,
    candidate: EntryCandidate,
    base_score: int,
    missing_plan: bool,
) -> dict[str, object]:
    reasons: list[str] = []
    warnings: list[str] = []
    blocking: list[str] = []
    score = min(base_score, 10)

    if candidate.model not in PROBE_ENTRY_SUPPORTED_MODELS:
        blocking.append("轻仓试错只适用于回踩型或订单块承接型，不适用于追涨突破。")

    support_zone = candidate.support_zone
    if support_zone is None:
        blocking.append("轻仓试错也必须依托明确的支撑区、需求区或订单块。")
    elif support_zone.level not in {ZoneLevel.A, ZoneLevel.B}:
        blocking.append("轻仓试错只接受日线 A/B 级支撑或需求区。")
    elif support_zone.fragility_score >= 2 or "many_touches" in support_zone.tags:
        blocking.append("轻仓试错依托的支撑区已经被明显消耗。")
    else:
        reasons.append(
            f"允许围绕日线 {support_zone.level.value} 级支撑/需求区 {support_zone.low:.2f}-{support_zone.high:.2f} 轻仓试错。"
        )

    if missing_plan:
        blocking.append("轻仓试错也必须能明确给出止损位和第一止盈位。")

    rr = candidate.risk_reward_ratio
    if rr is None:
        blocking.append("轻仓试错缺少可计算的盈亏比。")
    elif rr < PROBE_ENTRY_MIN_RR:
        blocking.append("轻仓试错要求盈亏比至少 1.5:1。")

    if not context.is_trend_healthy:
        blocking.append("日线趋势已转弱，不做轻仓试错开仓。")
    if not context.is_m60_trend_healthy:
        blocking.append("60分钟结构未保持抬升，不做轻仓试错开仓。")
    if context.market_state == "down":
        blocking.append("大盘同步转弱，暂停轻仓试错。")
    if context.sector_state == "weak":
        blocking.append("板块偏弱，暂不做轻仓试错。")
    if not context.liquidity_ok:
        blocking.append("流动性不足，不适合轻仓试错。")
    if context.weekly_background == "C":
        blocking.append("周线背景为 C，轻仓试错也不放行。")

    relaxable_blocks: list[str] = []
    for item in candidate.hard_blocking_reasons:
        if _is_relaxable_for_probe(item):
            relaxable_blocks.append(item)
        else:
            blocking.append(item)

    if relaxable_blocks:
        reasons.append("标准开仓还差最后一层确认，但允许先按轻仓试错跟踪。")
        warnings.extend(relaxable_blocks)

    for item in candidate.blocking_reasons:
        if "当前不接近明确支撑区" in item or "当前未回到有效订单块/需求区" in item:
            blocking.append(item)
        elif "板块偏弱" in item:
            blocking.append(item)
        else:
            warnings.append(item)

    allowed = score >= PROBE_ENTRY_ALLOW_THRESHOLD and not blocking
    return {
        "score": score,
        "allowed": allowed,
        "reasons": list(dict.fromkeys(reasons)),
        "warnings": list(dict.fromkeys(warnings)),
        "blocking": list(dict.fromkeys(blocking)),
    }


def _evaluate_t_reentry(
    context: EntryContext,
    candidate: EntryCandidate,
    base_score: int,
    missing_plan: bool,
) -> dict[str, object]:
    reasons: list[str] = []
    warnings: list[str] = []
    blocking: list[str] = []
    score = min(base_score, 10)

    if candidate.model not in T_REENTRY_SUPPORTED_MODELS:
        blocking.append("做T回补只适用于回踩型或订单块承接型，不适用于追涨突破。")

    support_zone = candidate.support_zone
    if support_zone is None:
        blocking.append("做T回补缺少明确的支撑区、需求区或订单块。")
    else:
        _evaluate_t_support_zone(support_zone, reasons, warnings, blocking)

    if not context.is_trend_healthy:
        blocking.append("日线趋势已转弱，当前不适合做T回补。")
    if not context.is_m60_trend_healthy:
        blocking.append("60分钟结构没有维持抬升，当前不适合做T回补。")
    if context.market_state == "down":
        blocking.append("大盘同步转弱，暂停做T回补。")
    if context.sector_state == "weak":
        blocking.append("板块偏弱，做T回补成功率不足。")
    if not context.liquidity_ok:
        blocking.append("流动性不足，不适合做T回补。")

    if missing_plan:
        blocking.append("做T回补也必须能明确给出止损位和第一止盈位。")

    rr = candidate.risk_reward_ratio
    if rr is None:
        blocking.append("做T回补缺少可计算的盈亏比。")
    elif rr < T_REENTRY_MIN_RR:
        blocking.append("做T回补要求盈亏比至少 1.5:1。")
    elif rr < STANDARD_MIN_RR:
        reasons.append(f"作为 T 仓回补，允许把盈亏比放宽到 {rr:.2f}。")

    relaxable_blocks: list[str] = []
    for item in candidate.hard_blocking_reasons:
        if _is_relaxable_for_t(item):
            relaxable_blocks.append(item)
        else:
            blocking.append(item)

    if relaxable_blocks:
        reasons.append("标准开仓未完全通过，但可按 T 仓回补放宽小周期确认或空间要求。")
        warnings.extend(relaxable_blocks)

    for item in candidate.blocking_reasons:
        if "相对强度不足" in item:
            warnings.append("做T回补对相对强度可适度放松，但只适用于轻仓回补。")
        elif "近期已被反复测试" in item:
            warnings.append(item)
        elif "板块偏弱" in item:
            blocking.append(item)
        else:
            warnings.append(item)

    allowed = score >= T_REENTRY_ALLOW_THRESHOLD and not blocking
    watch = score >= T_REENTRY_WATCH_THRESHOLD and not blocking and not allowed
    return {
        "score": score,
        "allowed": allowed,
        "watch": watch,
        "reasons": list(dict.fromkeys(reasons)),
        "warnings": list(dict.fromkeys(warnings)),
        "blocking": list(dict.fromkeys(blocking)),
    }


def _evaluate_t_support_zone(
    support_zone: PriceZone,
    reasons: list[str],
    warnings: list[str],
    blocking: list[str],
) -> None:
    if support_zone.level in {ZoneLevel.A, ZoneLevel.B}:
        reasons.append(
            f"做T回补依托日线 {support_zone.level.value} 级支撑/需求区 {support_zone.low:.2f}-{support_zone.high:.2f}。"
        )
    elif support_zone.level == ZoneLevel.C and _is_high_quality_c_support(support_zone):
        reasons.append(
            f"当前只依托高质量 C 级支撑区 {support_zone.low:.2f}-{support_zone.high:.2f}，仅允许轻仓 T 仓回补。"
        )
        warnings.append("高质量 C 级支撑只适合轻仓做T，不适合标准开仓。")
    else:
        blocking.append("做T回补必须靠近日线 A/B 级支撑，或极高质量的 C 级需求区。")

    if support_zone.fragility_score >= 2 or "many_touches" in support_zone.tags:
        blocking.append("支撑区已被明显消耗，做T回补性价比不足。")


def _is_relaxable_for_t(reason: str) -> bool:
    return any(marker in reason for marker in T_REENTRY_RELAXABLE_BLOCK_MARKERS)


def _is_relaxable_for_probe(reason: str) -> bool:
    return any(marker in reason for marker in PROBE_ENTRY_RELAXABLE_BLOCK_MARKERS)


def _is_high_quality_c_support(zone: PriceZone) -> bool:
    tags = set(zone.tags)
    confluence = 0
    if "with_fvg" in tags:
        confluence += 1
    if "with_order_block" in tags or "order_block" in tags:
        confluence += 1
    if "with_liquidity" in tags:
        confluence += 1
    if "with_large_liquidity" in tags:
        confluence += 1
    return confluence >= 3 and zone.fragility_score <= 1
