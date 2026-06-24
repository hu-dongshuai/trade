from __future__ import annotations

from enum import StrEnum


class Action(StrEnum):
    HOLD = "hold"
    REDUCE = "reduce"
    STOP_LOSS = "stop_loss"
    EXIT_ALL = "exit_all"


class Priority(StrEnum):
    NORMAL = "normal"
    HIGH = "high"
    IMMEDIATE = "immediate"


class ZoneLevel(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class EntryAction(StrEnum):
    ALLOW_ENTRY = "allow_entry"
    WATCH_ENTRY = "watch_entry"
    REJECT_ENTRY = "reject_entry"
