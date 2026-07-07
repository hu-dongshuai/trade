from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from sell_monitor.config import ObsidianMonitorConfig
from sell_monitor.domain.enums import Action
from sell_monitor.domain.models import AlertReviewRecord, Bar, Decision, PriceZone
from sell_monitor.notifier.symbol_display import normalize_symbol_name
from sell_monitor.notifier.zone_chart_renderer import render_weekly_zone_chart
from sell_monitor.review.alert_review_service import format_review_status


SELL_SIGNAL_ACTIONS = {Action.REDUCE, Action.STOP_LOSS, Action.EXIT_ALL}
LATEST_ZONES_START = "<!-- SELL_MONITOR_LATEST_ZONES_START -->"
LATEST_ZONES_END = "<!-- SELL_MONITOR_LATEST_ZONES_END -->"
DAILY_TRIGGER_FILENAME = "当日应卖出.md"
LEGACY_DAILY_TRIGGER_FILENAME = "当天触发.md"
MONITOR_TABLE_HEADER = "| 检测时间 | 股票代码 | 结论 | 动作 | 分数 | 价格 | 原因/提示 | 下一步 | 取消条件 | 复盘 |"
MONITOR_TABLE_SEPARATOR = "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- |"
DAILY_TRIGGER_TITLE = "# 当日应卖出"
DAILY_TRIGGER_TABLE_HEADER = "| 时间 | 股票代码 | 卖出动作 | 分数 | 价格 | 原因 | 建议 | 复盘 |"
DAILY_TRIGGER_TABLE_SEPARATOR = "| --- | --- | --- | ---: | ---: | --- | --- | --- |"


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

    def apply_review_updates(self, reviewed_alerts: list[AlertReviewRecord]) -> None:
        if not reviewed_alerts:
            return
        self.monitor_dir.mkdir(parents=True, exist_ok=True)
        alerts_by_symbol: dict[str, list[AlertReviewRecord]] = {}
        for alert in reviewed_alerts:
            alerts_by_symbol.setdefault(alert.symbol, []).append(alert)

        for symbol, alerts in alerts_by_symbol.items():
            path = self.monitor_dir / f"{_safe_filename(symbol)}.md"
            if not path.exists():
                continue
            previous = path.read_text(encoding="utf-8")
            updated = _apply_review_updates_to_content(previous, alerts, expected_cells=_expected_cell_count(MONITOR_TABLE_HEADER))
            path.write_text(updated, encoding="utf-8")

        daily_path = _resolve_daily_trigger_path(self.monitor_dir)
        if daily_path.exists():
            previous = daily_path.read_text(encoding="utf-8")
            updated = _apply_review_updates_to_content(
                previous,
                reviewed_alerts,
                expected_cells=_expected_cell_count(DAILY_TRIGGER_TABLE_HEADER),
            )
            daily_path.write_text(updated, encoding="utf-8")


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
    review_cell = _default_review_cell(decision)
    display_value = normalize_symbol_name(symbol, decision.symbol_name if decision else symbol_name) or symbol
    return (
        f"| {time_cell} | {display_value} | {conclusion} | {action} | {score} | {price} | "
        f"{_table_cell(reason)} | {_table_cell(next_step)} | {_table_cell(cancel_condition)} | {_table_cell(review_cell)} |"
    )


def _format_daily_trigger_row(decision: Decision, now: datetime) -> str:
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    display_value = normalize_symbol_name(decision.symbol, decision.symbol_name) or decision.symbol
    return (
        f"| {_format_time_cell(now_text, True)} | {display_value} | {decision.action.value} | {decision.total_score} | "
        f"{_format_price_cell(decision.current_price)} | {_table_cell(_join_reasons(decision.reasons))} | "
        f"{_table_cell(decision.next_step)} | {_table_cell(_default_review_cell(decision))} |"
    )


def _default_review_cell(decision: Decision | None) -> str:
    if decision is None or decision.action not in SELL_SIGNAL_ACTIONS:
        return "-"
    return "待复盘"


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
    path = _resolve_daily_trigger_path(monitor_dir)
    previous = _load_daily_trigger_previous(path, monitor_dir)
    rows = [_format_daily_trigger_row(decision, now) for decision in sell_decisions]
    path.write_text(_prepend_daily_trigger_rows(previous, rows), encoding="utf-8")


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
        "回填补齐检测记录",
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
    monitor_table = _format_table(MONITOR_TABLE_HEADER, MONITOR_TABLE_SEPARATOR, [row] + existing_rows)
    return f"{title}\n\n{zone_section}{monitor_table}\n"


def _prepend_daily_trigger_rows(previous: str, rows: list[str]) -> str:
    title, body = _split_daily_trigger_title(previous)
    existing_rows = _extract_table_rows(
        body,
        DAILY_TRIGGER_TABLE_HEADER,
        DAILY_TRIGGER_TABLE_SEPARATOR,
        expected_cells=_expected_cell_count(DAILY_TRIGGER_TABLE_HEADER),
    )
    daily_table = _format_table(DAILY_TRIGGER_TABLE_HEADER, DAILY_TRIGGER_TABLE_SEPARATOR, rows + existing_rows)
    return f"{title}\n\n{daily_table}\n"


def _split_title(previous: str, symbol: str) -> tuple[str, str]:
    lines = previous.splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0], "\n".join(lines[1:]).strip()
    return f"# {symbol} 监控记录", previous.strip()


def _split_daily_trigger_title(previous: str) -> tuple[str, str]:
    lines = previous.splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0], "\n".join(lines[1:]).strip()
    return DAILY_TRIGGER_TITLE, previous.strip()


def _resolve_daily_trigger_path(monitor_dir: Path) -> Path:
    return monitor_dir / DAILY_TRIGGER_FILENAME


def _load_daily_trigger_previous(path: Path, monitor_dir: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    legacy_path = monitor_dir / LEGACY_DAILY_TRIGGER_FILENAME
    if legacy_path.exists():
        return legacy_path.read_text(encoding="utf-8")
    return f"{DAILY_TRIGGER_TITLE}\n\n"


def _format_latest_zone_section(symbol: str, chart_ref: str) -> str:
    lines = [
        LATEST_ZONES_START,
        f'<img src="{chart_ref}" alt="{symbol} 最新支撑压力图" style="width: 40%; max-width: 40%;" />',
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
    return _extract_table_rows(
        body,
        MONITOR_TABLE_HEADER,
        MONITOR_TABLE_SEPARATOR,
        expected_cells=_expected_cell_count(MONITOR_TABLE_HEADER),
    )


def _extract_table_rows(body: str, header: str, separator: str, expected_cells: int) -> list[str]:
    rows: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        if line == header or line == separator:
            continue
        if _looks_like_table_row(line):
            rows.append(_normalize_row_columns(line, expected_cells))
    return rows


def _looks_like_table_row(line: str) -> bool:
    return bool(re.match(r"^\| (?:<span[^>]*>)?\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", line))


def _format_table(header: str, separator: str, rows: list[str]) -> str:
    return "\n".join([header, separator, *rows, ""])


def _apply_review_updates_to_content(
    previous: str,
    alerts: list[AlertReviewRecord],
    expected_cells: int,
) -> str:
    updated_lines: list[str] = []
    for raw_line in previous.splitlines():
        line = raw_line
        if _looks_like_table_row(line.strip()):
            normalized = _normalize_row_columns(line.strip(), expected_cells)
            matched = _find_matching_alert(normalized, alerts)
            if matched is not None:
                normalized = _replace_last_cell(normalized, format_review_status(matched))
            line = normalized
        updated_lines.append(line)
    return "\n".join(updated_lines) + ("\n" if previous.endswith("\n") else "")


def _find_matching_alert(line: str, alerts: list[AlertReviewRecord]) -> AlertReviewRecord | None:
    for alert in alerts:
        ts_text = alert.alert_ts.strftime("%Y-%m-%d %H:%M:%S")
        if ts_text not in line:
            continue
        if alert.symbol in line:
            return alert
        if alert.symbol_name and alert.symbol_name in line:
            return alert
    return None


def _expected_cell_count(header: str) -> int:
    return header.count("|") - 1


def _normalize_row_columns(line: str, expected_cells: int) -> str:
    cells = _split_table_cells(line)
    if not cells:
        return line
    if len(cells) < expected_cells:
        cells.extend(["-"] * (expected_cells - len(cells)))
    elif len(cells) > expected_cells:
        cells = cells[: expected_cells - 1] + [" | ".join(cells[expected_cells - 1 :])]
    return _format_row(cells)


def _split_table_cells(line: str) -> list[str]:
    text = line.strip()
    if not text.startswith("|"):
        return []
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for ch in text[1:]:
        if escaped:
            current.append(ch)
            escaped = False
            continue
        if ch == "\\":
            current.append(ch)
            escaped = True
            continue
        if ch == "|":
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    if cells and cells[-1] == "":
        cells.pop()
    return cells


def _format_row(cells: list[str]) -> str:
    return "| " + " | ".join(cell.strip() for cell in cells) + " |"


def _replace_last_cell(line: str, value: str) -> str:
    cells = _split_table_cells(line)
    if not cells:
        return line
    cells[-1] = _table_cell(value)
    return _format_row(cells)


def _full_width_frontmatter() -> str:
    return "---\ncssclasses: full-width-note\n---"


def _compose_document(title: str, body: str) -> str:
    frontmatter = _full_width_frontmatter()
    if body:
        return f"{frontmatter}\n\n{title}\n\n{body}\n"
    return f"{frontmatter}\n\n{title}\n"


def _strip_frontmatter(content: str) -> str:
    if not content.startswith("---"):
        return content
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        return content
    for idx in range(1, len(lines)):
        if lines[idx] == "---":
            return "\n".join(lines[idx + 1 :]).lstrip("\n")
    return content


def _initial_content(symbol: str) -> str:
    return _compose_document(f"# {symbol} 鐩戞帶璁板綍", "")


def _prepend_entry(previous: str, entry: str) -> str:
    title, body = _split_title(previous, "unknown")
    merged = f"{entry}{body and body + chr(10)}".rstrip()
    return _compose_document(title, merged)


def _prepend_monitor_run(previous: str, row: str, symbol: str, chart_ref: str) -> str:
    title, body = _split_title(previous, symbol)
    body = _remove_latest_zone_section(body)
    body = _remove_embedded_zone_tables(body)
    existing_rows = _extract_monitor_rows(body)
    zone_section = _format_latest_zone_section(symbol, chart_ref)
    monitor_table = _format_table(MONITOR_TABLE_HEADER, MONITOR_TABLE_SEPARATOR, [row] + existing_rows)
    return _compose_document(title, f"{zone_section}{monitor_table}".rstrip())


def _prepend_daily_trigger_rows(previous: str, rows: list[str]) -> str:
    title, body = _split_daily_trigger_title(previous)
    existing_rows = _extract_table_rows(
        body,
        DAILY_TRIGGER_TABLE_HEADER,
        DAILY_TRIGGER_TABLE_SEPARATOR,
        expected_cells=_expected_cell_count(DAILY_TRIGGER_TABLE_HEADER),
    )
    daily_table = _format_table(DAILY_TRIGGER_TABLE_HEADER, DAILY_TRIGGER_TABLE_SEPARATOR, rows + existing_rows)
    return _compose_document(title, daily_table.rstrip())


def _split_title(previous: str, symbol: str) -> tuple[str, str]:
    previous = _strip_frontmatter(previous)
    lines = previous.splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0], "\n".join(lines[1:]).strip()
    return f"# {symbol} 鐩戞帶璁板綍", previous.strip()


def _split_daily_trigger_title(previous: str) -> tuple[str, str]:
    previous = _strip_frontmatter(previous)
    lines = previous.splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0], "\n".join(lines[1:]).strip()
    return DAILY_TRIGGER_TITLE, previous.strip()


def _load_daily_trigger_previous(path: Path, monitor_dir: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    legacy_path = monitor_dir / LEGACY_DAILY_TRIGGER_FILENAME
    if legacy_path.exists():
        return legacy_path.read_text(encoding="utf-8")
    return _compose_document(DAILY_TRIGGER_TITLE, "")
