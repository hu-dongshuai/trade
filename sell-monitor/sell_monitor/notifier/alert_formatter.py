from __future__ import annotations

from sell_monitor.domain.models import Decision
from sell_monitor.notifier.symbol_display import display_symbol


def format_decision(decision: Decision) -> str:
    reasons = "\n".join(f"  {idx + 1}. {reason}" for idx, reason in enumerate(decision.reasons))
    return (
        f"[{display_symbol(decision.symbol, decision.symbol_name)}] action={decision.action.value} score={decision.total_score}\n"
        f"reasons:\n{reasons}\n"
        f"next: {decision.next_step}\n"
        f"cancel: {decision.cancel_condition}"
    )
