from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from sell_monitor.config import ObsidianEntryConfig
from sell_monitor.domain.enums import EntryAction
from sell_monitor.domain.models import Bar, EntryDecision, PriceZone
from sell_monitor.notifier.symbol_display import normalize_symbol_name
from sell_monitor.notifier.zone_chart_renderer import render_weekly_zone_chart


ENTRY_ALLOW_ACTIONS = {EntryAction.ALLOW_ENTRY}
ENTRY_TABLE_HEADER = "| 检测时间 | 股票代码 | 是否允许开仓 | 开仓模型 | 开仓分数 | 计划挂单价 | 止损价 | 第一止盈位 | 盈亏比 | 原因/阻断原因 | 下一步建议 |"
ENTRY_TABLE_SEPARATOR = "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |"
DAILY_ENTRY_TITLE = "# 当日可开仓候选"
DAILY_ENTRY_HEADER = "| 时间 | 股票代码 | 开仓模型 | 开仓分数 | 计划挂单价 | 止损价 | 第一止盈位 | 盈亏比 | 原因 |"
DAILY_ENTRY_SEPARATOR = "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |"
LATEST_ZONES_START = "<!-- ENTRY_MONITOR_LATEST_ZONES_START -->"
LATEST_ZONES_END = "<!-- ENTRY_MONITOR_LATEST_ZONES_END -->"
STATIC_PROVIDER_NOTICE_MARKERS = (
    "当前使用的是静态数据源 static",
    "examples\\market_data.json",
    "akshare/baostock",
)


class ObsidianEntryRunRecorder:
    def __init__(self, config: ObsidianEntryConfig) -> None:
        self.monitor_dir = config.monitor_dir

    def write_run(
        self,
        symbols: list[str],
        decisions: list[EntryDecision],
        notices: list[str],
        symbol_names: dict[str, str] | None = None,
        zone_snapshots: dict[str, list[PriceZone]] | None = None,
        daily_bar_snapshots: dict[str, list[Bar]] | None = None,
        now: datetime | None = None,
    ) -> None:
        self.monitor_dir.mkdir(parents=True, exist_ok=True)
        decisions_by_symbol = {decision.symbol: decision for decision in decisions}
        notices_by_symbol = _group_notices_by_symbol(notices)
        symbol_names = symbol_names or {}
        zone_snapshots = zone_snapshots or {}
        daily_bar_snapshots = daily_bar_snapshots or {}
        now = now or datetime.now()

        for symbol in symbols:
            safe_symbol = _safe_filename(symbol)
            path = self.monitor_dir / f"{safe_symbol}.md"
            previous = path.read_text(encoding="utf-8") if path.exists() else f"# {safe_symbol} 开仓检查记录\n\n"
            chart_path = render_weekly_zone_chart(
                self.monitor_dir / "assets",
                safe_symbol,
                daily_bar_snapshots.get(symbol, []),
                zone_snapshots.get(symbol, []),
            )
            row = _format_row(
                symbol=safe_symbol,
                decision=decisions_by_symbol.get(symbol),
                notices=notices_by_symbol.get(symbol, []),
                symbol_name=symbol_names.get(symbol),
                now=now,
            )
            path.write_text(_prepend_entry_run(previous, row, safe_symbol, f"assets/{chart_path.name}"), encoding="utf-8")

        _write_daily_allowed_summary(self.monitor_dir, decisions, now)


def _format_row(
    symbol: str,
    decision: EntryDecision | None,
    notices: list[str],
    symbol_name: str | None,
    now: datetime,
) -> str:
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    allow = decision is not None and decision.allowed
    time_cell = f'<span style="color:red">{now_text}</span>' if allow else now_text
    display_value = normalize_symbol_name(symbol, decision.symbol_name if decision else symbol_name) or symbol
    allow_text = "允许" if allow else "不允许"
    model = decision.entry_model if decision else "none"
    score = str(decision.entry_score) if decision else "0"
    reason_parts: list[str] = []
    if decision:
        reason_parts.extend(decision.reasons)
        reason_parts.extend(decision.blocking_reasons)
    reason_parts.extend(_visible_notices(notices))
    reasons = "；".join(reason_parts) if reason_parts else "未识别出明确开仓模型"
    next_step = decision.next_step if decision else "继续观察"
    return (
        f"| {time_cell} | {display_value} | {allow_text} | {model} | {score} | {_fmt(decision.planned_entry_price if decision else None)} | "
        f"{_fmt(decision.stop_loss_price if decision else None)} | {_fmt(decision.first_take_profit_price if decision else None)} | "
        f"{_fmt(decision.risk_reward_ratio if decision else None)} | {_cell(reasons)} | {_cell(next_step)} |"
    )


def _write_daily_allowed_summary(monitor_dir: Path, decisions: list[EntryDecision], now: datetime) -> None:
    allowed = [decision for decision in decisions if decision.allowed]
    if not allowed:
        return
    path = monitor_dir / "当日可开仓候选.md"
    previous = path.read_text(encoding="utf-8") if path.exists() else f"{DAILY_ENTRY_TITLE}\n\n"
    rows = []
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    for decision in allowed:
        display_value = normalize_symbol_name(decision.symbol, decision.symbol_name) or decision.symbol
        rows.append(
            f"| <span style=\"color:red\">{now_text}</span> | {display_value} | {decision.entry_model} | {decision.entry_score} | "
            f"{_fmt(decision.planned_entry_price)} | {_fmt(decision.stop_loss_price)} | {_fmt(decision.first_take_profit_price)} | "
            f"{_fmt(decision.risk_reward_ratio)} | {_cell('；'.join(decision.reasons))} |"
        )
    existing_rows = _extract_rows(previous, DAILY_ENTRY_HEADER, DAILY_ENTRY_SEPARATOR)
    path.write_text(
        "\n".join([DAILY_ENTRY_TITLE, "", DAILY_ENTRY_HEADER, DAILY_ENTRY_SEPARATOR, *rows, *existing_rows, ""]),
        encoding="utf-8",
    )


def _prepend_entry_run(previous: str, row: str, symbol: str, chart_ref: str) -> str:
    title, body = _split_title(previous, symbol)
    body = _remove_latest_zone_section(body)
    existing_rows = _extract_rows(body, ENTRY_TABLE_HEADER, ENTRY_TABLE_SEPARATOR)
    if _should_skip_duplicate_static_row(existing_rows, row):
        table = "\n".join([ENTRY_TABLE_HEADER, ENTRY_TABLE_SEPARATOR, *existing_rows, ""])
    else:
        table = "\n".join([ENTRY_TABLE_HEADER, ENTRY_TABLE_SEPARATOR, row, *existing_rows, ""])
    zone_section = "\n".join(
        [
            LATEST_ZONES_START,
            f"![{symbol} 最新支撑压力图]({chart_ref})",
            "",
            LATEST_ZONES_END,
            "",
            "",
        ]
    )
    return f"{title}\n\n{zone_section}{table}\n"


def _split_title(previous: str, symbol: str) -> tuple[str, str]:
    lines = previous.splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0], "\n".join(lines[1:]).strip()
    return f"# {symbol} 开仓检查记录", previous.strip()


def _extract_rows(content: str, header: str, separator: str) -> list[str]:
    rows: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if stripped in {header, separator}:
            continue
        if _looks_like_table_row(stripped):
            rows.append(stripped)
    return rows


def _looks_like_table_row(line: str) -> bool:
    return bool(re.match(r"^\| (?:<span[^>]*>)?\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", line))


def _remove_latest_zone_section(content: str) -> str:
    if LATEST_ZONES_START not in content or LATEST_ZONES_END not in content:
        return content.strip()
    before, _, rest = content.partition(LATEST_ZONES_START)
    _, _, after = rest.partition(LATEST_ZONES_END)
    return f"{before.strip()}\n{after.strip()}".strip()


def _group_notices_by_symbol(notices: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for notice in notices:
        if not notice.startswith("[") or "]" not in notice:
            continue
        symbol = _safe_filename(notice[1 : notice.index("]")])
        grouped.setdefault(symbol, []).append(notice)
    return grouped


def _visible_notices(notices: list[str]) -> list[str]:
    hidden_patterns = (
        "已命中本地缓存",
        "回溯补齐检测记录",
        "历史关键价位已导出到",
        "日线关键价位已导出到",
        "尝试更新网络数据源",
        "已回退到本地缓存",
    )
    return [notice for notice in notices if not any(pattern in notice for pattern in hidden_patterns)]


def _should_skip_duplicate_static_row(existing_rows: list[str], new_row: str) -> bool:
    if not _is_static_provider_row(new_row) or not existing_rows:
        return False
    latest_row = existing_rows[0]
    if not _is_static_provider_row(latest_row):
        return False
    new_ts = _extract_row_timestamp(new_row)
    latest_ts = _extract_row_timestamp(latest_row)
    if new_ts is None or latest_ts is None:
        return True
    return new_ts.date() == latest_ts.date()


def _is_static_provider_row(row: str) -> bool:
    marker_hits = sum(1 for marker in STATIC_PROVIDER_NOTICE_MARKERS if marker in row)
    return marker_hits >= 2


def _extract_row_timestamp(row: str) -> datetime | None:
    match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", row)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _cell(value: str) -> str:
    return value.replace("\r", " ").replace("\n", "<br>").replace("|", "\\|").strip() or "-"


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def _safe_filename(value: str) -> str:
    return "".join(ch for ch in value.strip() if ch.isalnum() or ch in {"_", "-", "."}) or "unknown"
