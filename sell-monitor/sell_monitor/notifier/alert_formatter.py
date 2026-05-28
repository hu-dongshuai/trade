from __future__ import annotations

from sell_monitor.domain.models import Decision


def format_decision(decision: Decision) -> str:
    reasons = "\n".join(f"  {idx + 1}. {reason}" for idx, reason in enumerate(decision.reasons))
    return (
        f"[{decision.symbol}] action={decision.action.value} score={decision.total_score} "
        f"priority={decision.priority.value}\n"
        f"reasons:\n{reasons}\n"
        f"next: {decision.next_step}\n"
        f"cancel: {decision.cancel_condition}"
    )

