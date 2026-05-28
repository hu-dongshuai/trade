from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo


CHINA_TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class TradingSession:
    start: time
    end: time

    def contains(self, current: time) -> bool:
        return self.start <= current <= self.end


A_SHARE_SESSIONS = (
    TradingSession(time(9, 30), time(11, 30)),
    TradingSession(time(13, 0), time(15, 0)),
)


def now_china() -> datetime:
    return datetime.now(CHINA_TZ)


def is_a_share_trading_time(current: datetime | None = None) -> bool:
    current = current.astimezone(CHINA_TZ) if current else now_china()
    if current.weekday() >= 5:
        return False
    current_time = current.time()
    return any(session.contains(current_time) for session in A_SHARE_SESSIONS)


def describe_a_share_trading_hours() -> str:
    return "A股常规交易时段为交易日 09:30-11:30、13:00-15:00"
