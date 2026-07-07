from __future__ import annotations

from sell_monitor.domain.models import EntryDecision
from sell_monitor.notifier.symbol_display import display_symbol


def format_entry_decision(decision: EntryDecision) -> str:
    reasons = "\n".join(f"  {idx + 1}. {reason}" for idx, reason in enumerate(decision.reasons)) or "  -"
    blocking = (
        "\n".join(f"  {idx + 1}. {reason}" for idx, reason in enumerate(decision.blocking_reasons))
        if decision.blocking_reasons
        else "  -"
    )
    return (
        f"[{display_symbol(decision.symbol, decision.symbol_name)}] action={decision.action.value} score={decision.entry_score} "
        f"allowed={'yes' if decision.allowed else 'no'} route={decision.entry_route} model={decision.entry_model}\n"
        f"plan: entry={_fmt(decision.planned_entry_price)} stop={_fmt(decision.stop_loss_price)} "
        f"tp1={_fmt(decision.first_take_profit_price)} rr={_fmt(decision.risk_reward_ratio)}\n"
        f"route: {_route_label(decision.entry_route)}\n"
        f"reasons:\n{reasons}\n"
        f"blocking:\n{blocking}\n"
        f"next: {decision.next_step}"
    )


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def _route_label(route: str) -> str:
    if route == "standard_entry":
        return "标准开仓"
    if route == "t_reentry":
        return "T仓回补"
    return "禁止回补"
