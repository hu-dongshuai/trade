from __future__ import annotations

from datetime import datetime

from sell_monitor.domain.enums import Action, Priority
from sell_monitor.domain.models import Decision, FundamentalAssessment, FundamentalSnapshot


def load_fundamental_assessment(provider, symbol: str, as_of_dt: datetime | None = None) -> FundamentalAssessment:
    snapshot = None
    try:
        if as_of_dt is not None and hasattr(provider, "get_fundamental_snapshot_until"):
            snapshot = provider.get_fundamental_snapshot_until(symbol, as_of_dt)
        elif hasattr(provider, "get_fundamental_snapshot"):
            snapshot = provider.get_fundamental_snapshot(symbol)
    except Exception as exc:
        return FundamentalAssessment(
            symbol=symbol,
            level="neutral",
            quality_score=0.0,
            score_adjustment=0,
            reasons=[f"基本面数据暂不可用，按中性处理：{exc}"],
        )
    return assess_fundamentals(symbol, snapshot)


def assess_fundamentals(symbol: str, snapshot: FundamentalSnapshot | None) -> FundamentalAssessment:
    if snapshot is None:
        return FundamentalAssessment(symbol, "neutral", 0.0, 0, ["未取得基本面数据，按中性处理"])
    if snapshot.event_risk:
        note = f"：{snapshot.event_note}" if snapshot.event_note else ""
        return FundamentalAssessment(symbol, "event_risk", 0.0, 2, [f"存在重大事件风险{note}，卖出风险分 +2"])

    score = 0.0
    reasons: list[str] = []

    if _growth_ok(snapshot.revenue_yoy, snapshot.previous_revenue_yoy, 10.0):
        score += 2.0
        reasons.append("营收同比增长较好")
    elif _positive(snapshot.revenue_yoy):
        score += 1.0
        reasons.append("营收同比为正")

    profit_yoy = snapshot.deducted_net_profit_yoy
    if profit_yoy is None:
        profit_yoy = snapshot.net_profit_yoy
    if _growth_ok(profit_yoy, snapshot.previous_deducted_net_profit_yoy, 10.0):
        score += 2.0
        reasons.append("扣非净利润或净利润同比增长较好")
    elif _positive(profit_yoy):
        score += 1.0
        reasons.append("扣非净利润或净利润同比为正")

    margin_score = _margin_score(snapshot)
    score += margin_score
    if margin_score >= 1.5:
        reasons.append("毛利率和净利率保持稳定")
    elif margin_score > 0:
        reasons.append("部分利润率保持稳定")

    cashflow_ratio = _normalize_ratio(snapshot.operating_cashflow_to_profit)
    if cashflow_ratio is not None:
        if cashflow_ratio >= 1.0:
            score += 2.0
            reasons.append("经营现金流覆盖净利润")
        elif cashflow_ratio >= 0.8:
            score += 1.5
            reasons.append("经营现金流质量尚可")

    roe = _normalize_percent(snapshot.roe)
    if roe is not None:
        if roe >= 15.0:
            score += 1.0
            reasons.append("ROE 高于 15%")
        elif roe >= 10.0:
            score += 0.8
            reasons.append("ROE 高于 10%")

    debt_asset_ratio = _normalize_percent(snapshot.debt_asset_ratio)
    if debt_asset_ratio is not None and debt_asset_ratio <= 60.0:
        score += 1.0
        reasons.append("资产负债率处于可控区间")

    if snapshot.pe_percentile is not None and snapshot.pe_percentile <= 70.0:
        score += 0.5
        reasons.append("估值分位未明显透支")

    if score >= 8.0:
        return FundamentalAssessment(symbol, "strong", score, -1, reasons + ["基本面强，普通卖出信号降一级"])
    if score < 5.0:
        weak_reasons = reasons or ["核心基本面指标不足或偏弱"]
        return FundamentalAssessment(symbol, "weak", score, 1, weak_reasons + ["基本面偏弱，卖出风险分 +1"])
    return FundamentalAssessment(symbol, "neutral", score, 0, reasons + ["基本面中性，不调整技术分"])


def apply_fundamental_weight(decision: Decision, assessment: FundamentalAssessment) -> Decision:
    if assessment.score_adjustment == 0:
        return decision
    if decision.action == Action.STOP_LOSS or _is_manual_hard_exit(decision):
        return decision

    adjusted_score = max(0, decision.total_score + assessment.score_adjustment)
    action, priority, next_step, cancel_condition = _decision_terms(
        adjusted_score,
        assessment,
        decision.next_step,
        decision.cancel_condition,
    )
    return Decision(
        symbol=decision.symbol,
        action=action,
        total_score=adjusted_score,
        priority=priority,
        reasons=decision.reasons + assessment.reasons,
        next_step=next_step,
        cancel_condition=cancel_condition,
        symbol_name=decision.symbol_name,
        current_price=decision.current_price,
    )


def _decision_terms(
    total_score: int,
    assessment: FundamentalAssessment,
    fallback_next: str,
    fallback_cancel: str,
) -> tuple[Action, Priority, str, str]:
    if total_score > 5:
        return (
            Action.EXIT_ALL,
            Priority.IMMEDIATE,
            "清仓卖出；基本面权重已纳入风险分",
            "需要后续重新站回关键价位，并且基本面风险缓解",
        )
    if total_score > 3:
        return (
            Action.REDUCE,
            Priority.HIGH,
            "减仓，优先减掉 50% 风险仓位；基本面权重已纳入风险分",
            "价格重新站稳关键价位，且卖点信号消失",
        )
    if assessment.level == "strong":
        return (
            Action.HOLD,
            Priority.NORMAL,
            "基本面强，普通技术卖出信号降级为观察；等待破位确认",
            "跌破日线 A/B 级支撑、15 分钟/60 分钟破位，或基本面转弱",
        )
    return Action.HOLD, Priority.NORMAL, fallback_next, fallback_cancel


def _is_manual_hard_exit(decision: Decision) -> bool:
    return any("硬性清仓规则" in reason for reason in decision.reasons)


def _growth_ok(latest: float | None, previous: float | None, threshold: float) -> bool:
    if latest is None or latest < threshold:
        return False
    return previous is None or previous >= 0


def _positive(value: float | None) -> bool:
    return value is not None and value > 0


def _margin_score(snapshot: FundamentalSnapshot) -> float:
    score = 0.0
    if _stable_or_better(snapshot.gross_margin, snapshot.previous_gross_margin):
        score += 0.75
    if _stable_or_better(snapshot.net_margin, snapshot.previous_net_margin):
        score += 0.75
    return score


def _stable_or_better(latest: float | None, previous: float | None) -> bool:
    if latest is None or previous is None:
        return False
    return latest >= previous - 1.0


def _normalize_ratio(value: float | None) -> float | None:
    if value is None:
        return None
    if abs(value) > 5.0:
        return value / 100.0
    return value


def _normalize_percent(value: float | None) -> float | None:
    if value is None:
        return None
    if abs(value) <= 1.0:
        return value * 100.0
    return value
