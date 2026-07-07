from __future__ import annotations

from sell_monitor.domain.models import Bar, PriceZone
from sell_monitor.entry.models import EntryCandidate, EntryContext
from sell_monitor.entry.risk_plan import plan_breakout_trade, plan_pullback_trade


def detect_entry_candidates(
    context: EntryContext,
    daily_bars: list[Bar],
    m15_bars: list[Bar],
) -> list[EntryCandidate]:
    candidates: list[EntryCandidate] = []
    pullback = _detect_pullback_entry(context, daily_bars, m15_bars)
    if pullback:
        candidates.append(pullback)
    order_block = _detect_order_block_entry(context, daily_bars, m15_bars)
    if order_block:
        candidates.append(order_block)
    breakout = _detect_breakout_entry(context, daily_bars, m15_bars)
    if breakout:
        candidates.append(breakout)
    return sorted(candidates, key=lambda item: (item.score, item.risk_reward_ratio or 0), reverse=True)


def _detect_pullback_entry(
    context: EntryContext,
    daily_bars: list[Bar],
    m15_bars: list[Bar],
) -> EntryCandidate | None:
    support = _nearest_support_zone(context)
    if support is None:
        return None
    target = _nearest_resistance_zone(context, context.current_price)
    planned_entry_price, stop_loss_price, first_take_profit_price, rr = plan_pullback_trade(
        context.current_price,
        support,
        target,
        m15_bars,
    )
    score = 0
    reasons: list[str] = []
    blocking_reasons: list[str] = []
    hard_blocking_reasons: list[str] = []
    _apply_multi_timeframe_gate(
        context,
        reasons,
        blocking_reasons,
        hard_blocking_reasons,
        require_accumulation=True,
    )

    if context.is_trend_healthy:
        score += 2
        reasons.append("日线趋势保持上行，处于健康上升趋势")
    else:
        hard_blocking_reasons.append("日线趋势不够健康，不符合回踩型做多背景")

    if context.is_m60_trend_healthy:
        score += 1
        reasons.append("60分钟结构保持抬升，回踩更容易获得承接")
    else:
        hard_blocking_reasons.append("60分钟结构未保持抬升，暂不做回踩开仓")

    if context.daily_relative_strength_ok:
        score += 1
        reasons.append("个股近5到10日动能仍强于普通震荡状态")
    else:
        blocking_reasons.append("个股近期相对强度不足，回踩后再起概率下降")

    if context.liquidity_ok:
        score += 1
        reasons.append(f"日均成交额约 {context.avg_daily_turnover / 100000000:.2f} 亿，流动性达标")
    else:
        hard_blocking_reasons.append("日均成交额偏低，流动性不足，不做回踩开仓")

    if _is_near_zone(context.current_price, support):
        score += 2
        reasons.append(f"当前接近日线 {support.level.value} 级支撑/需求区 {support.low:.2f}-{support.high:.2f}")
    else:
        blocking_reasons.append("当前不接近明确支撑区，仍处于中间模糊区")

    if support.level.value == "C" and not _is_high_quality_c_support(support):
        hard_blocking_reasons.append("当前仅接近普通C级支撑区，默认只观察，不直接开仓")
    elif support.level.value == "C":
        blocking_reasons.append("当前为C级支撑区，必须等待更强确认后再考虑开仓")

    if _has_bullish_reclaim(m15_bars):
        score += 2
        reasons.append("15分钟出现承接确认，价格回踩后重新转强")
    else:
        hard_blocking_reasons.append("15分钟尚未出现明确承接确认")

    if _pullback_volume_is_healthy(m15_bars):
        score += 1
        reasons.append("回踩阶段未见明显放量破位")
    else:
        hard_blocking_reasons.append("回踩过程量价不健康，存在放量走弱迹象")

    if rr is not None and rr >= 1.5:
        score += 1
        reasons.append(f"第一止盈位空间充足，盈亏比约 {rr:.2f}")
    else:
        hard_blocking_reasons.append("第一止盈位空间不足，盈亏比低于 1.5:1")

    if "with_fvg" in support.tags or "with_order_block" in support.tags:
        score += 1
        reasons.append("支撑区存在失衡区/订单块共振")
    if "with_liquidity" in support.tags:
        score += 1
        reasons.append("支撑区附近存在流动性，回踩承接质量更高")
    if "with_large_liquidity" in support.tags:
        score += 1
        reasons.append("支撑区叠加大量流动性，低吸承接胜率更高")

    if "many_touches" in support.tags or support.fragility_score >= 2:
        hard_blocking_reasons.append("支撑区已被反复消耗，回踩胜率下降")
    if "recently_tested" in support.tags and "fresh_zone" not in support.tags:
        blocking_reasons.append("支撑区近期已被反复测试，需等待更强承接")
    if _resistance_too_close(context, support, target):
        hard_blocking_reasons.append("上方压力过近，空间不足，不适合做回踩开仓")

    score += _multi_timeframe_score_bonus(context, reasons, blocking_reasons)
    return EntryCandidate(
        model="pullback_buy",
        score=min(score, 10),
        planned_entry_price=planned_entry_price,
        stop_loss_price=stop_loss_price,
        first_take_profit_price=first_take_profit_price,
        risk_reward_ratio=rr,
        reasons=reasons,
        blocking_reasons=blocking_reasons,
        hard_blocking_reasons=hard_blocking_reasons,
        support_zone=support,
        target_zone=target,
    )


def _detect_order_block_entry(
    context: EntryContext,
    daily_bars: list[Bar],
    m15_bars: list[Bar],
) -> EntryCandidate | None:
    order_block = _nearest_tagged_zone(context, {"with_order_block", "order_block", "demand"})
    if order_block is None:
        return None
    target = _nearest_resistance_zone(context, context.current_price)
    planned_entry_price, stop_loss_price, first_take_profit_price, rr = plan_pullback_trade(
        context.current_price,
        order_block,
        target,
        m15_bars,
    )
    score = 0
    reasons: list[str] = []
    blocking_reasons: list[str] = []
    hard_blocking_reasons: list[str] = []
    _apply_multi_timeframe_gate(
        context,
        reasons,
        blocking_reasons,
        hard_blocking_reasons,
        require_accumulation=True,
    )

    if context.is_trend_healthy:
        score += 2
        reasons.append("趋势背景支持订单块承接型做多")
    else:
        hard_blocking_reasons.append("趋势背景偏弱，订单块承接胜率不足")

    if context.is_m60_trend_healthy:
        score += 1
        reasons.append("60分钟结构同步向上，订单块承接更稳")
    else:
        hard_blocking_reasons.append("60分钟未同步向上，订单块承接暂不放行")

    if context.daily_relative_strength_ok:
        score += 1
        reasons.append("个股近期相对强度尚可")
    else:
        blocking_reasons.append("个股近期相对强度不足")

    if context.liquidity_ok:
        score += 1
        reasons.append(f"日均成交额约 {context.avg_daily_turnover / 100000000:.2f} 亿，流动性达标")
    else:
        hard_blocking_reasons.append("流动性不足，不做订单块承接开仓")

    if _is_near_zone(context.current_price, order_block):
        score += 2
        reasons.append(f"当前回到有效订单块/需求区 {order_block.low:.2f}-{order_block.high:.2f}")
    else:
        hard_blocking_reasons.append("当前未回到有效订单块/需求区")

    if "with_fvg" in order_block.tags:
        score += 2
        reasons.append("订单块伴随失衡区，共振质量更高")
    if "with_liquidity" in order_block.tags or "with_large_liquidity" in order_block.tags:
        score += 1
        reasons.append("订单块附近存在流动性，承接质量更高")

    if _has_bullish_reclaim(m15_bars):
        score += 1
        reasons.append("15分钟承接后重新转强")
    else:
        hard_blocking_reasons.append("小周期未给出明确承接确认")

    if rr is not None and rr >= 1.5:
        score += 1
        reasons.append(f"第一止盈位空间充足，盈亏比约 {rr:.2f}")
    else:
        hard_blocking_reasons.append("第一止盈位空间不足，盈亏比低于 1.5:1")

    if "many_touches" in order_block.tags or order_block.fragility_score >= 2:
        hard_blocking_reasons.append("订单块已被反复回踩，承接边际下降")
    if "fresh_zone" not in order_block.tags and "with_fvg" not in order_block.tags:
        blocking_reasons.append("订单块不够新鲜，需等待更强确认")
    if _resistance_too_close(context, order_block, target):
        hard_blocking_reasons.append("上方压力过近，订单块承接空间不足")

    score += _multi_timeframe_score_bonus(context, reasons, blocking_reasons)
    return EntryCandidate(
        model="order_block_buy",
        score=min(score, 10),
        planned_entry_price=planned_entry_price,
        stop_loss_price=stop_loss_price,
        first_take_profit_price=first_take_profit_price,
        risk_reward_ratio=rr,
        reasons=reasons,
        blocking_reasons=blocking_reasons,
        hard_blocking_reasons=hard_blocking_reasons,
        support_zone=order_block,
        target_zone=target,
    )


def _detect_breakout_entry(
    context: EntryContext,
    daily_bars: list[Bar],
    m15_bars: list[Bar],
) -> EntryCandidate | None:
    breakout_level = _recent_breakout_level(m15_bars)
    if breakout_level is None:
        return None
    target = _nearest_resistance_zone(context, breakout_level)
    planned_entry_price, stop_loss_price, first_take_profit_price, rr = plan_breakout_trade(
        breakout_level,
        target,
        m15_bars,
    )
    score = 0
    reasons: list[str] = []
    blocking_reasons: list[str] = []
    hard_blocking_reasons: list[str] = []
    _apply_multi_timeframe_gate(
        context,
        reasons,
        blocking_reasons,
        hard_blocking_reasons,
        require_accumulation=False,
    )

    if context.is_trend_healthy:
        score += 2
        reasons.append("趋势健康，突破后更容易延续")
    else:
        hard_blocking_reasons.append("趋势不健康，突破延续性不足")

    if context.is_m60_trend_healthy:
        score += 2
        reasons.append("60分钟结构顺势，突破延续性更强")
    else:
        hard_blocking_reasons.append("60分钟结构不顺势，突破型开仓直接过滤")

    if context.daily_relative_strength_ok:
        score += 1
        reasons.append("个股近期动能保持强势")
    else:
        hard_blocking_reasons.append("个股近期相对强度不足，不做追涨突破")

    if context.liquidity_ok:
        score += 1
        reasons.append(f"日均成交额约 {context.avg_daily_turnover / 100000000:.2f} 亿，追涨流动性达标")
    else:
        hard_blocking_reasons.append("流动性不足，不做突破追涨")

    if _is_true_breakout(m15_bars):
        score += 3
        reasons.append("15分钟实体突破关键价位，且伴随放量")
    else:
        hard_blocking_reasons.append("当前更像普通波动或假突破，不满足真突破条件")

    if _is_first_pullback_holding(m15_bars):
        score += 2
        reasons.append("突破后的第一次回调承接正常")
    else:
        hard_blocking_reasons.append("突破后的首次回调承接不够清晰")

    if rr is not None and rr >= 1.5:
        score += 1
        reasons.append(f"突破后第一目标位空间充足，盈亏比约 {rr:.2f}")
    else:
        hard_blocking_reasons.append("突破后目标位空间不足，盈亏比低于 1.5:1")

    if context.sector_state in {"strong", "up"}:
        score += 1
        reasons.append("板块强于平均，突破成功率更高")
    else:
        blocking_reasons.append("板块未明显走强，突破胜率打折")

    if _resistance_too_close(context, None, target, breakout_level):
        hard_blocking_reasons.append("突破上方立即遇到高等级压力，不做追涨突破")

    score += _multi_timeframe_score_bonus(context, reasons, blocking_reasons, breakout_mode=True)
    return EntryCandidate(
        model="breakout_buy",
        score=min(score, 10),
        planned_entry_price=planned_entry_price,
        stop_loss_price=stop_loss_price,
        first_take_profit_price=first_take_profit_price,
        risk_reward_ratio=rr,
        reasons=reasons,
        blocking_reasons=blocking_reasons,
        hard_blocking_reasons=hard_blocking_reasons,
        target_zone=target,
    )


def _nearest_support_zone(context: EntryContext) -> PriceZone | None:
    candidates = [zone for zone in context.daily_support_zones if zone.high <= context.current_price * 1.03]
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda zone: (
            zone.level.value,
            -zone.importance_score,
            zone.fragility_score,
            abs(context.current_price - zone.high),
        ),
    )
    return ranked[0]


def _nearest_tagged_zone(context: EntryContext, tags: set[str]) -> PriceZone | None:
    candidates = [
        zone for zone in context.daily_support_zones if tags.intersection(zone.tags) and zone.high <= context.current_price * 1.04
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda zone: abs(context.current_price - zone.high))


def _nearest_resistance_zone(context: EntryContext, base_price: float) -> PriceZone | None:
    candidates = [zone for zone in context.daily_resistance_zones if zone.high > base_price]
    if not candidates:
        return None
    return min(candidates, key=lambda zone: zone.low - base_price if zone.low > base_price else 0.0)


def _is_near_zone(price: float, zone: PriceZone) -> bool:
    if zone.contains(price):
        return True
    gap = min(abs(price - zone.low), abs(price - zone.high))
    return gap / max(price, 0.01) <= 0.03


def _has_bullish_reclaim(m15_bars: list[Bar]) -> bool:
    if len(m15_bars) < 12:
        return False
    last = m15_bars[-1]
    prev = m15_bars[-2]
    recent = m15_bars[-11:-1]
    avg_volume = sum(bar.volume for bar in recent) / len(recent)
    upper_wick_ratio = last.upper_wick / max(last.range, 0.01)
    bearish_count = sum(1 for bar in m15_bars[-4:-1] if bar.is_bearish and bar.volume > avg_volume * 1.2)
    return (
        last.is_bullish
        and last.close > prev.high
        and last.volume >= avg_volume * 1.3
        and upper_wick_ratio <= 0.35
        and bearish_count < 2
    )


def _pullback_volume_is_healthy(m15_bars: list[Bar]) -> bool:
    if len(m15_bars) < 10:
        return False
    recent = m15_bars[-6:]
    selloff_bars = [bar for bar in recent[:-1] if bar.close <= bar.open]
    if not selloff_bars:
        return True
    reclaim_volume = recent[-1].volume
    heavy_bearish = [bar for bar in selloff_bars if bar.volume > reclaim_volume * 1.1]
    return len(heavy_bearish) == 0


def _recent_breakout_level(m15_bars: list[Bar]) -> float | None:
    if len(m15_bars) < 10:
        return None
    prior_high = max(bar.high for bar in m15_bars[-10:-2])
    last = m15_bars[-1]
    prev = m15_bars[-2]
    if prev.close > prior_high or last.close > prior_high:
        return round(prior_high, 2)
    return None


def _is_true_breakout(m15_bars: list[Bar]) -> bool:
    if len(m15_bars) < 10:
        return False
    last = m15_bars[-1]
    prev = m15_bars[-2]
    prior_high = max(bar.high for bar in m15_bars[-10:-2])
    recent_volumes = [bar.volume for bar in m15_bars[-8:-1]]
    avg_volume = sum(recent_volumes) / len(recent_volumes)
    upper_wick_ratio = last.upper_wick / max(last.range, 0.01)
    return (
        last.close > prior_high
        and last.body >= last.range * 0.6
        and last.volume >= avg_volume * 1.5
        and upper_wick_ratio <= 0.25
        and prev.close >= prev.open
    )


def _is_first_pullback_holding(m15_bars: list[Bar]) -> bool:
    if len(m15_bars) < 5:
        return False
    breakout_bar = m15_bars[-2]
    last = m15_bars[-1]
    avg_volume = sum(bar.volume for bar in m15_bars[-11:-1]) / min(len(m15_bars[-11:-1]), 10)
    return (
        last.low >= breakout_bar.open
        and last.close >= breakout_bar.close * 0.995
        and last.low >= breakout_bar.low
        and last.volume <= breakout_bar.volume * 0.9
        and breakout_bar.volume >= avg_volume * 1.2
    )


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


def _resistance_too_close(
    context: EntryContext,
    support_zone: PriceZone | None,
    target_zone: PriceZone | None,
    base_price: float | None = None,
) -> bool:
    if target_zone is None:
        return True
    entry_price = base_price or context.current_price
    upside = target_zone.low - entry_price
    if upside <= 0:
        return True
    support_low = support_zone.low if support_zone else entry_price * 0.98
    downside = entry_price - support_low
    if downside <= 0:
        return True
    return upside / downside < 2.3


def _apply_multi_timeframe_gate(
    context: EntryContext,
    reasons: list[str],
    blocking_reasons: list[str],
    hard_blocking_reasons: list[str],
    require_accumulation: bool,
) -> None:
    if context.weekly_background == "A":
        reasons.append("周线背景为A类：位置更适合观察回踩吸筹")
    elif context.weekly_background == "B":
        reasons.append("周线背景为B类：位置中性，需依赖更强确认")
    else:
        hard_blocking_reasons.append("周线背景为C类：更接近高位压力或周线走弱，不按吸筹开仓处理")

    if require_accumulation and context.accumulation_score <= 3:
        hard_blocking_reasons.append("多周期洗盘吸筹辅助分过低，当前更像普通弱势回调")
    elif require_accumulation and context.accumulation_score <= 6:
        blocking_reasons.append("多周期洗盘吸筹结构仅为中性，需等待更强承接后再评估")


def _multi_timeframe_score_bonus(
    context: EntryContext,
    reasons: list[str],
    blocking_reasons: list[str],
    breakout_mode: bool = False,
) -> int:
    bonus = 0
    if context.weekly_background == "A":
        bonus += 2 if not breakout_mode else 1
    elif context.weekly_background == "B":
        bonus += 1

    if context.accumulation_score >= 7:
        bonus += 1
        reasons.append(f"多周期洗盘吸筹辅助分 {context.accumulation_score}/10，结构偏强")
    elif breakout_mode and context.accumulation_score <= 3:
        blocking_reasons.append("多周期结构偏弱，突破延续性需要额外观察")
    elif context.accumulation_score >= 4:
        reasons.append(f"多周期洗盘吸筹辅助分 {context.accumulation_score}/10，结构中性")

    for extra_reason in context.accumulation_reasons[:3]:
        if extra_reason not in reasons:
            reasons.append(extra_reason)
    return bonus
