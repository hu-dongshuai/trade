from __future__ import annotations

from typing import TypeAlias

from sell_monitor.domain.models import Bar, PriceZone, Signal

BarList: TypeAlias = list[Bar]
ZoneList: TypeAlias = list[PriceZone]
SignalList: TypeAlias = list[Signal]

