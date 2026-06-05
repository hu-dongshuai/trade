from __future__ import annotations

from typing import Protocol

from sell_monitor.domain.models import Decision
from sell_monitor.notifier.alert_formatter import format_decision
from sell_monitor.notifier.symbol_display import display_symbol


class AlertChannel(Protocol):
    def send(self, subject: str, message: str) -> None: ...


class ConsoleChannel:
    def send(self, subject: str, message: str) -> None:
        print(message)


class ConsoleAlertDispatcher:
    def __init__(self, channels: list[AlertChannel] | None = None, subject_prefix: str = "[SellMonitor]") -> None:
        self.channels = channels or [ConsoleChannel()]
        self.subject_prefix = subject_prefix

    def dispatch(self, decision: Decision) -> None:
        message = format_decision(decision)
        subject = (
            f"{self.subject_prefix} {display_symbol(decision.symbol, decision.symbol_name)} "
            f"{decision.action.value} score={decision.total_score}"
        )
        for channel in self.channels:
            channel.send(subject, message)
