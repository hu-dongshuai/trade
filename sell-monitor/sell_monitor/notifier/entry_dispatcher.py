from __future__ import annotations

from typing import Protocol

from sell_monitor.domain.models import EntryDecision
from sell_monitor.notifier.entry_formatter import format_entry_decision
from sell_monitor.notifier.symbol_display import display_symbol


class EntryAlertChannel(Protocol):
    def send(self, subject: str, message: str) -> None: ...


class EntryConsoleChannel:
    def send(self, subject: str, message: str) -> None:
        print(message)


class EntryAlertDispatcher:
    def __init__(self, channels: list[EntryAlertChannel] | None = None, subject_prefix: str = "[EntryMonitor]") -> None:
        self.channels = channels or [EntryConsoleChannel()]
        self.subject_prefix = subject_prefix

    def dispatch(self, decision: EntryDecision) -> None:
        message = format_entry_decision(decision)
        subject = (
            f"{self.subject_prefix} {display_symbol(decision.symbol, decision.symbol_name)} "
            f"{decision.action.value} score={decision.entry_score}"
        )
        for channel in self.channels:
            channel.send(subject, message)
