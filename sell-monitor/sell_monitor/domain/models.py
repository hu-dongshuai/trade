from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sell_monitor.domain.enums import Action, EntryAction, Priority, ZoneLevel


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


@dataclass(frozen=True)
class FundamentalSnapshot:
    symbol: str
    ts: datetime
    report_date: datetime | None = None
    revenue_yoy: float | None = None
    previous_revenue_yoy: float | None = None
    net_profit_yoy: float | None = None
    deducted_net_profit_yoy: float | None = None
    previous_deducted_net_profit_yoy: float | None = None
    gross_margin: float | None = None
    previous_gross_margin: float | None = None
    net_margin: float | None = None
    previous_net_margin: float | None = None
    roe: float | None = None
    operating_cashflow_to_profit: float | None = None
    debt_asset_ratio: float | None = None
    pe_percentile: float | None = None
    event_risk: bool = False
    event_note: str | None = None


@dataclass(frozen=True)
class FundamentalAssessment:
    symbol: str
    level: str
    quality_score: float
    score_adjustment: int
    reasons: list[str]


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
    importance_score: int = 0
    fragility_score: int = 0
    invalidation_price: float | None = None

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
            importance_score=max(self.importance_score, other.importance_score),
            fragility_score=max(self.fragility_score, other.fragility_score),
            invalidation_price=self.invalidation_price,
        )


@dataclass(frozen=True)
class Signal:
    name: str
    score: int
    triggered: bool
    reason: str
    triggered_at: datetime | None = None
    trigger_price: float | None = None


@dataclass(frozen=True)
class DailyContext:
    symbol: str
    current_price: float
    daily_zones: list[PriceZone]
    active_zone: PriceZone | None
    daily_trend: str
    market_state: str
    sector_state: str
    daily_bars: list[Bar] = field(default_factory=list)
    sell_warning_active: bool = False
    sell_warning_reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Decision:
    symbol: str
    action: Action
    total_score: int
    priority: Priority
    reasons: list[str]
    next_step: str
    cancel_condition: str
    symbol_name: str | None = None
    current_price: float | None = None
    hold_protection_score: int = 0
    hold_protection_reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AlertReviewRecord:
    alert_id: str
    symbol: str
    action: Action
    alert_ts: datetime
    price: float
    score: int
    reasons: list[str]
    symbol_name: str | None = None
    review_window_days: int = 5
    review_status: str = "pending"
    reviewed_at: datetime | None = None
    drawdown_pct: float | None = None
    runup_pct: float | None = None


@dataclass(frozen=True)
class EntryDecision:
    symbol: str
    action: EntryAction
    allowed: bool
    entry_score: int
    entry_route: str
    entry_model: str
    planned_entry_price: float | None
    stop_loss_price: float | None
    first_take_profit_price: float | None
    risk_reward_ratio: float | None
    reasons: list[str]
    blocking_reasons: list[str]
    next_step: str
    symbol_name: str | None = None
    current_price: float | None = None


@dataclass(frozen=True)
class MonitorRunResult:
    decisions: list[Decision]
    notices: list[str]
    zone_snapshots: dict[str, list[PriceZone]] = field(default_factory=dict)
    daily_bar_snapshots: dict[str, list[Bar]] = field(default_factory=dict)
    reviewed_alerts: list[AlertReviewRecord] = field(default_factory=list)


@dataclass(frozen=True)
class EntryScanRunResult:
    decisions: list[EntryDecision]
    notices: list[str]
    zone_snapshots: dict[str, list[PriceZone]] = field(default_factory=dict)
    daily_bar_snapshots: dict[str, list[Bar]] = field(default_factory=dict)
