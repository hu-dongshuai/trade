from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from sell_monitor.config import ObsidianMonitorConfig
from sell_monitor.domain.enums import Action
from sell_monitor.domain.models import Bar, Decision, PriceZone
from sell_monitor.notifier.symbol_display import normalize_symbol_name
from sell_monitor.notifier.zone_chart_renderer import render_weekly_zone_chart


SELL_SIGNAL_ACTIONS = {Action.REDUCE, Action.STOP_LOSS, Action.EXIT_ALL}
LATEST_ZONES_START = "<!-- SELL_MONITOR_LATEST_ZONES_START -->"
LATEST_ZONES_END = "<!-- SELL_MONITOR_LATEST_ZONES_END -->"
MONITOR_TABLE_HEADER = "| 检测时间 | 股票代码 | 结论 | 动作 | 分数 | 价格 | 原因/提示 | 下一步 | 取消条件 |"
MONITOR_TABLE_SEPARATOR = "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |"


class ObsidianMarkdownChannel:
    def __init__(self, config: ObsidianMonitorConfig) -> None:
        self.monitor_dir = config.monitor_dir

    def send(self, subject: str, message: str) -> None:
        symbol = _extract_symbol(subject, message)
        self.monitor_dir.mkdir(parents=True, exist_ok=True)
        path = self.monitor_dir / f"{symbol}.md"
        previous = path.read_text(encoding="utf-8") if path.exists() else _initial_content(symbol)
        entry = _format_entry(subject, message)
        path.write_text(_prepend_entry(previous, entry), encoding="utf-8")


class ObsidianMonitorRunRecorder:
    def __init__(self, config: ObsidianMonitorConfig) -> None:
        self.monitor_dir = config.monitor_dir

    def write_run(
        self,
        symbols: list[str],
        decisions: list[Decision],
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
            previous = path.read_text(encoding="utf-8") if path.exists() else _initial_content(safe_symbol)
            zones = zone_snapshots.get(symbol, [])
            daily_bars = daily_bar_snapshots.get(symbol, [])
            chart_path = render_weekly_zone_chart(self.monitor_dir / "assets", safe_symbol, daily_bars, zones)
            chart_ref = f"assets/{chart_path.name}"
            row = _format_run_row(
                symbol=safe_symbol,
                decision=decisions_by_symbol.get(symbol),
                notices=notices_by_symbol.get(symbol, []),
                symbol_name=symbol_names.get(symbol),
                now=now,
            )
            path.write_text(_prepend_monitor_run(previous, row, safe_symbol, chart_ref), encoding="utf-8")
        _write_daily_trigger_summary(self.monitor_dir, decisions, now)


def _extract_symbol(subject: str, message: str) -> str:
    if message.startswith("[") and "]" in message:
        return _safe_filename(message[1 : message.index("]")])
    subject_parts = subject.split()
    if len(subject_parts) >= 2:
        return _safe_filename(subject_parts[1])
    return "unknown"


def _safe_filename(value: str) -> str:
    return "".join(ch for ch in value.strip() if ch.isalnum() or ch in {"_", "-", "."}) or "unknown"


def _initial_content(symbol: str) -> str:
    return f"# {symbol} 监控记录\n\n"


def _format_entry(subject: str, message: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return "\n".join(
        [
            f"## {now}",
            "",
            f"- 主题: {subject}",
            "",
            "```text",
            message,
            "```",
            "",
        ]
    )


def _format_run_row(
    symbol: str,
    decision: Decision | None,
    notices: list[str],
    symbol_name: str | None,
    now: datetime,
) -> str:
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    has_sell_signal = decision is not None and decision.action in SELL_SIGNAL_ACTIONS
    time_cell = _format_time_cell(now_text, has_sell_signal)
    action = decision.action.value if decision else "none"
    score = str(decision.total_score) if decision else "0"
    price = _format_price_cell(decision.current_price if decision else None)
    conclusion = "卖出信号" if has_sell_signal else "未触发卖出信号"
    reason = _summarize_reasons(decision, notices)
    next_step = decision.next_step if decision else "继续观察"
    cancel_condition = decision.cancel_condition if decision else "-"
    display_value = normalize_symbol_name(symbol, decision.symbol_name if decision else symbol_name) or symbol
    return (
        f"| {time_cell} | {display_value} | {conclusion} | {action} | {score} | {price} | "
        f"{_table_cell(reason)} | {_table_cell(next_step)} | {_table_cell(cancel_condition)} |"
    )


def _format_time_cell(now_text: str, has_sell_signal: bool) -> str:
    if has_sell_signal:
        return f'<span style="color:red">{now_text}</span>'
    return now_text


def _group_notices_by_symbol(notices: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for notice in notices:
        symbol = _extract_notice_symbol(notice)
        if not symbol:
            continue
        grouped.setdefault(symbol, []).append(notice)
    return grouped


def _extract_notice_symbol(notice: str) -> str | None:
    if not notice.startswith("[") or "]" not in notice:
        return None
    return _safe_filename(notice[1 : notice.index("]")])


def _write_daily_trigger_summary(monitor_dir: Path, decisions: list[Decision], now: datetime) -> None:
    sell_decisions = [decision for decision in decisions if decision.action in SELL_SIGNAL_ACTIONS]
    if not sell_decisions:
        return
    path = monitor_dir / "当日触发.md"
    previous = path.read_text(encoding="utf-8") if path.exists() else "# 当日触发\n\n"
    entry = _format_daily_trigger_entry(sell_decisions, now)
    path.write_text(_prepend_entry(previous, entry), encoding="utf-8")


def _format_daily_trigger_entry(decisions: list[Decision], now: datetime) -> str:
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "| 时间 | 股票代码 | 卖出动作 | 分数 | 价格 | 原因 | 建议 |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for decision in decisions:
        display_value = normalize_symbol_name(decision.symbol, decision.symbol_name) or decision.symbol
        lines.append(
            f"| {_format_time_cell(now_text, True)} | {display_value} | {decision.action.value} | {decision.total_score} | {_format_price_cell(decision.current_price)} | "
            f"{_table_cell(_join_reasons(decision.reasons))} | {_table_cell(decision.next_step)} |"
        )
    lines.append("")
    return "\n".join(lines)


def _summarize_reasons(decision: Decision | None, notices: list[str]) -> str:
    parts: list[str] = []
    if decision:
        parts.extend(decision.reasons)
    parts.extend(_visible_notices(notices))
    if not parts:
        return "本轮检测正常，无额外提示"
    return "；".join(parts)


def _visible_notices(notices: list[str]) -> list[str]:
    return [notice for notice in notices if not _is_runtime_notice(notice)]


def _is_runtime_notice(notice: str) -> bool:
    runtime_patterns = (
        "已命中本地缓存",
        "回溯补齐检测记录",
        "历史关键价位已导出到",
        "日线关键价位已导出到",
        "本地缓存15分钟数据不足",
        "尝试更新网络数据源",
        "已回退到本地缓存",
        "不可用，已回退到",
    )
    return any(pattern in notice for pattern in runtime_patterns)


def _join_reasons(reasons: list[str]) -> str:
    return "；".join(reasons) if reasons else "-"


def _table_cell(value: str) -> str:
    return value.replace("\r", " ").replace("\n", "<br>").replace("|", "\\|").strip() or "-"


def _format_price_cell(price: float | None) -> str:
    if price is None:
        return "-"
    return f"{price:.2f}"


def _prepend_entry(previous: str, entry: str) -> str:
    lines = previous.splitlines()
    if lines and lines[0].startswith("# "):
        title = lines[0]
        body = "\n".join(lines[1:]).strip()
        return f"{title}\n\n{entry}{body and body + chr(10)}"
    body = previous.strip()
    return f"{entry}{body and body + chr(10)}"


def _prepend_monitor_run(previous: str, row: str, symbol: str, chart_ref: str) -> str:
    title, body = _split_title(previous, symbol)
    body = _remove_latest_zone_section(body)
    body = _remove_embedded_zone_tables(body)
    existing_rows = _extract_monitor_rows(body)
    zone_section = _format_latest_zone_section(symbol, chart_ref)
    monitor_table = _format_monitor_table([row] + existing_rows)
    return f"{title}\n\n{zone_section}{monitor_table}\n"


def _split_title(previous: str, symbol: str) -> tuple[str, str]:
    lines = previous.splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0], "\n".join(lines[1:]).strip()
    return f"# {symbol} 监控记录", previous.strip()


def _format_latest_zone_section(symbol: str, chart_ref: str) -> str:
    lines = [
        LATEST_ZONES_START,
        f"![{symbol} 最新支撑压力图]({chart_ref})",
        "",
        LATEST_ZONES_END,
        "",
        "",
    ]
    return "\n".join(lines)


def _remove_latest_zone_section(body: str) -> str:
    pattern = re.compile(
        rf"{re.escape(LATEST_ZONES_START)}.*?{re.escape(LATEST_ZONES_END)}\s*",
        flags=re.DOTALL,
    )
    return pattern.sub("", body).strip()


def _remove_embedded_zone_tables(body: str) -> str:
    pattern = re.compile(
        r"### 支撑压力位[^\S\r\n]*\r?\n[^\S\r\n]*\r?\n"
        r"\| 股票 \| 周期 \| 等级 \| 类型 \|.*?\r?\n"
        r"\| --- \| --- \| --- \| --- \|.*?\r?\n"
        r"(?:\|.*?\|[^\S\r\n]*\r?\n)+"
        r"[^\S\r\n]*(?:\r?\n)?",
        flags=re.DOTALL,
    )
    return pattern.sub("", body).strip()


def _extract_monitor_rows(body: str) -> list[str]:
    rows: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        if line == MONITOR_TABLE_HEADER or line == MONITOR_TABLE_SEPARATOR:
            continue
        if _looks_like_monitor_row(line):
            rows.append(line)
    return rows


def _looks_like_monitor_row(line: str) -> bool:
    return bool(re.match(r"^\| (?:<span[^>]*>)?\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", line))


def _format_monitor_table(rows: list[str]) -> str:
    return "\n".join([MONITOR_TABLE_HEADER, MONITOR_TABLE_SEPARATOR, *rows, ""])
