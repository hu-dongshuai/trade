from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from pathlib import Path

from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.domain.models import Position, UserRule
from sell_monitor.monitor.replay_decision import build_replay_decision
from sell_monitor.notifier.channels.obsidian import ObsidianMonitorRunRecorder
from sell_monitor.trading_time import CHINA_TZ


CHECKPOINT_TIMES = (
    time(9, 30),
    time(10, 30),
    time(11, 30),
    time(13, 0),
    time(14, 0),
    time(15, 0),
)


def backfill_missing_obsidian_records(
    provider,
    recorder: ObsidianMonitorRunRecorder,
    symbols: list[str],
    symbol_names: dict[str, str],
    positions: dict[str, Position],
    rules: dict[str, UserRule],
    current_time: datetime,
) -> list[str]:
    notices: list[str] = []
    targets = _target_checkpoints(current_time)
    if not targets:
        return notices

    for symbol in symbols:
        missing = _missing_checkpoints(recorder.monitor_dir, symbol, targets, current_time)
        if not missing:
            continue
        notices.append(f"[{symbol}] Obsidian 缺少 {len(missing)} 条历史检测记录，开始回溯补齐")
        position = positions.get(symbol)
        if position is None:
            position = Position(symbol=symbol, cost_price=0.0, quantity=1)
        for as_of_dt in missing:
            try:
                replay = build_replay_decision(
                    provider=provider,
                    symbol=symbol,
                    as_of_dt=as_of_dt.replace(tzinfo=None),
                    position=position,
                    rule=rules.get(symbol),
                )
            except MarketDataError as exc:
                notice = f"[{symbol}] {as_of_dt.strftime('%Y-%m-%d %H:%M:%S')} 回溯补齐失败：{exc}"
                recorder.write_run(
                    symbols=[symbol],
                    decisions=[],
                    notices=[notice],
                    symbol_names={symbol: symbol_names.get(symbol, symbol)},
                    zone_snapshots={symbol: []},
                    daily_bar_snapshots={symbol: []},
                    now=as_of_dt.replace(tzinfo=None),
                )
                notices.append(notice)
                continue
            provider_notices = []
            if hasattr(provider, "consume_notices"):
                provider_notices = provider.consume_notices()
            replay_notices = provider_notices + replay.notices + [
                f"[{symbol}] 回溯补齐检测记录（截至 {as_of_dt.strftime('%Y-%m-%d %H:%M:%S')}）"
            ]
            recorder.write_run(
                symbols=[symbol],
                decisions=[replay.decision],
                notices=replay_notices,
                symbol_names={symbol: symbol_names.get(symbol, symbol)},
                zone_snapshots={symbol: replay.zones},
                daily_bar_snapshots={symbol: replay.daily_bars},
                now=as_of_dt.replace(tzinfo=None),
            )
        notices.append(f"[{symbol}] 历史检测记录回溯补齐完成")
    return notices


def _missing_checkpoints(
    monitor_dir: Path,
    symbol: str,
    targets: list[datetime],
    current_time: datetime,
) -> list[datetime]:
    path = monitor_dir / f"{_safe_filename(symbol)}.md"
    existing_slots = _existing_record_slots(path)
    current_slot = _slot_key(current_time)
    return [target for target in targets if _slot_key(target) not in existing_slots and _slot_key(target) != current_slot]


def _target_checkpoints(current_time: datetime) -> list[datetime]:
    current = current_time.astimezone(CHINA_TZ) if current_time.tzinfo else current_time.replace(tzinfo=CHINA_TZ)
    dates = _recent_trading_dates(current.date(), previous_count=2)
    targets: list[datetime] = []
    current_slot = _slot_key(current)
    for trading_date in dates:
        for checkpoint_time in CHECKPOINT_TIMES:
            target = datetime.combine(trading_date, checkpoint_time, tzinfo=CHINA_TZ)
            if _slot_key(target) < current_slot:
                targets.append(target)
    return targets


def _recent_trading_dates(current_date, previous_count: int) -> list:
    dates = []
    day = current_date
    if _is_weekday(day):
        dates.append(day)
    day = current_date - timedelta(days=1)
    while len(dates) < previous_count + (1 if _is_weekday(current_date) else 0):
        if _is_weekday(day):
            dates.append(day)
        day -= timedelta(days=1)
    return sorted(dates)


def _is_weekday(day) -> bool:
    return day.weekday() < 5


def _existing_record_slots(path: Path) -> set[tuple[str, int]]:
    if not path.exists():
        return set()
    content = path.read_text(encoding="utf-8")
    slots = set()
    for match in re.finditer(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", content):
        try:
            slots.add(_slot_key(datetime.strptime(match.group(0), "%Y-%m-%d %H:%M:%S")))
        except ValueError:
            continue
    return slots


def _slot_key(value: datetime) -> tuple[str, int]:
    local = value.astimezone(CHINA_TZ) if value.tzinfo else value
    return local.strftime("%Y-%m-%d"), local.hour


def _safe_filename(value: str) -> str:
    return "".join(ch for ch in value.strip() if ch.isalnum() or ch in {"_", "-", "."}) or "unknown"
