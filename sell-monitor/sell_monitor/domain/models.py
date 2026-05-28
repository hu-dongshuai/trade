from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sell_monitor.domain.enums import Action, Priority, ZoneLevel


@dataclass(frozen=True)
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    ts: datetime


@dataclass(frozen=True)
class Position:
    symbol: str
    cost_price: float
    quantity: float


@dataclass(frozen=True)
class UserRule:
    symbol: str
    stop_loss: float | None = None
    take_profit: float | None = None
    hard_exit_note: str | None = None
    entry_reason: str | None = None


@dataclass
class PriceZone:
    name: str
    timeframe: str
    low: float
    high: float
    score: int = 0
    level: ZoneLevel = ZoneLevel.D
    tags: list[str] = field(default_factory=list)
    touches: int = 0

    def overlaps(self, other: "PriceZone") -> bool:
        return self.low <= other.high and other.low <= self.high

    def contains(self, price: float) -> bool:
        return self.low <= price <= self.high

    def merge(self, other: "PriceZone") -> "PriceZone":
        merged_tags = sorted(set(self.tags + other.tags))
        return PriceZone(
            name=f"{self.name}+{other.name}",
            timeframe=self.timeframe,
            low=min(self.low, other.low),
            high=max(self.high, other.high),
            score=self.score + other.score,
            level=self.level,
            tags=merged_tags,
            touches=max(self.touches, other.touches),
        )


@dataclass(frozen=True)
class Signal:
    name: str
    score: int
    triggered: bool
    reason: str


@dataclass(frozen=True)
class DailyContext:
    symbol: str
    current_price: float
    daily_zones: list[PriceZone]
    active_zone: PriceZone | None
    daily_trend: str
    market_state: str
    sector_state: str


@dataclass(frozen=True)
class Decision:
    symbol: str
    action: Action
    total_score: int
    priority: Priority
    reasons: list[str]
    next_step: str
    cancel_condition: str


@dataclass(frozen=True)
class MonitorRunResult:
    decisions: list[Decision]
    notices: list[str]
