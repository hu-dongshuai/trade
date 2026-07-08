from __future__ import annotations

import re
from datetime import datetime
from html import escape
from pathlib import Path

from sell_monitor.config import ObsidianEntryConfig
from sell_monitor.domain.models import Bar, EntryDecision, PriceZone
from sell_monitor.notifier.symbol_display import normalize_symbol_name
from sell_monitor.notifier.zone_chart_renderer import render_weekly_zone_chart


ENTRY_COLUMNS = (
    ("检测时间", "12%"),
    ("股票代码", "8%"),
    ("是否允许开仓", "8%"),
    ("开仓路线/模型", "12%"),
    ("开仓分数", "6%"),
    ("计划挂单价", "8%"),
    ("止损价", "8%"),
    ("第一止盈位", "8%"),
    ("盈亏比", "6%"),
    ("原因/阻断原因", "16%"),
    ("下一步建议", "8%"),
)
DAILY_ENTRY_COLUMNS = (
    ("时间", "14%"),
    ("股票代码", "10%"),
    ("开仓路线/模型", "14%"),
    ("开仓分数", "7%"),
    ("计划挂单价", "9%"),
    ("止损价", "9%"),
    ("第一止盈位", "9%"),
    ("盈亏比", "7%"),
    ("原因", "21%"),
)
DAILY_ENTRY_TITLE = "# 当日可开仓候选"
LATEST_ZONES_START = "<!-- ENTRY_MONITOR_LATEST_ZONES_START -->"
LATEST_ZONES_END = "<!-- ENTRY_MONITOR_LATEST_ZONES_END -->"
ENTRY_TABLE_START = "<!-- ENTRY_MONITOR_TABLE_START -->"
ENTRY_TABLE_END = "<!-- ENTRY_MONITOR_TABLE_END -->"
DAILY_TABLE_START = "<!-- ENTRY_MONITOR_DAILY_TABLE_START -->"
DAILY_TABLE_END = "<!-- ENTRY_MONITOR_DAILY_TABLE_END -->"
ENTRY_TABLE_CLASS = "trade-monitor-table entry-monitor-table"
DAILY_ENTRY_TABLE_CLASS = "trade-monitor-table entry-monitor-daily-table"
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
            previous = path.read_text(encoding="utf-8") if path.exists() else f"# {safe_symbol} 开仓检查记录\n"
            zones = zone_snapshots.get(symbol, [])
            daily_bars = daily_bar_snapshots.get(symbol, [])
            chart_path = render_weekly_zone_chart(
                self.monitor_dir / "assets",
                safe_symbol,
                daily_bars,
                zones,
            )
            row_cells = _build_row_cells(
                symbol=safe_symbol,
                decision=decisions_by_symbol.get(symbol),
                notices=notices_by_symbol.get(symbol, []),
                symbol_name=symbol_names.get(symbol),
                now=now,
            )
            reference_price = _resolve_entry_reference_price(decisions_by_symbol.get(symbol), daily_bars)
            path.write_text(
                _prepend_entry_run(previous, row_cells, safe_symbol, f"assets/{chart_path.name}", zones, reference_price),
                encoding="utf-8",
            )

        _write_daily_allowed_summary(self.monitor_dir, decisions, now)


def _build_row_cells(
    symbol: str,
    decision: EntryDecision | None,
    notices: list[str],
    symbol_name: str | None,
    now: datetime,
) -> list[str]:
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    allow = decision is not None and decision.allowed
    time_cell = f'<span class="trade-monitor-alert-time">{now_text}</span>' if allow else now_text
    display_value = normalize_symbol_name(symbol, decision.symbol_name if decision else symbol_name) or symbol
    allow_text = "允许" if allow else "不允许"
    route_model = _route_model_text(decision) if decision else "禁止回补 / none"
    score = str(decision.entry_score) if decision else "0"
    reason_parts: list[str] = []
    if decision:
        reason_parts.extend(decision.reasons)
        reason_parts.extend(decision.blocking_reasons)
    reason_parts.extend(_visible_notices(notices))
    reasons = "；".join(reason_parts) if reason_parts else "未识别出明确开仓模型"
    next_step = decision.next_step if decision else "继续观察"
    return [
        time_cell,
        display_value,
        allow_text,
        route_model,
        score,
        _fmt(decision.planned_entry_price if decision else None),
        _fmt(decision.stop_loss_price if decision else None),
        _fmt(decision.first_take_profit_price if decision else None),
        _fmt(decision.risk_reward_ratio if decision else None),
        reasons,
        next_step,
    ]


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
            [
                f'<span class="trade-monitor-alert-time">{now_text}</span>',
                display_value,
                _route_model_text(decision),
                str(decision.entry_score),
                _fmt(decision.planned_entry_price),
                _fmt(decision.stop_loss_price),
                _fmt(decision.first_take_profit_price),
                _fmt(decision.risk_reward_ratio),
                "；".join(decision.reasons),
            ]
        )
    existing_rows = _extract_rows(previous, expected_cells=len(DAILY_ENTRY_COLUMNS), start_marker=DAILY_TABLE_START, end_marker=DAILY_TABLE_END)
    body = _remove_marked_section(previous, DAILY_TABLE_START, DAILY_TABLE_END).strip()
    title, rest = _split_daily_trigger_title(body)
    table = _render_table(DAILY_ENTRY_COLUMNS, rows + existing_rows, DAILY_TABLE_START, DAILY_TABLE_END)
    path.write_text(f"{title}\n\n{table}\n", encoding="utf-8")


def _prepend_entry_run(
    previous: str,
    row_cells: list[str],
    symbol: str,
    chart_ref: str,
    zones: list[PriceZone],
    reference_price: float | None,
) -> str:
    title, body = _split_title(previous, symbol)
    body = _remove_latest_zone_section(body)
    existing_rows = _extract_rows(body, expected_cells=len(ENTRY_COLUMNS), start_marker=ENTRY_TABLE_START, end_marker=ENTRY_TABLE_END)
    if _should_skip_duplicate_static_row(existing_rows, row_cells):
        rows = existing_rows
    else:
        rows = [row_cells, *existing_rows]
    focus_block = _format_focus_zone_block(zones, reference_price)
    zone_section = "\n".join(
        [
            LATEST_ZONES_START,
            *([focus_block, ""] if focus_block else []),
            f'<img src="{chart_ref}" alt="{symbol} 最新支撑压力图" style="width: 40%; max-width: 40%;" />',
            "",
            LATEST_ZONES_END,
            "",
            "",
        ]
    )
    table = _render_table(ENTRY_COLUMNS, rows, ENTRY_TABLE_START, ENTRY_TABLE_END)
    return f"{title}\n\n{zone_section}{table}\n"


def _render_table(
    columns: tuple[tuple[str, str], ...],
    rows: list[list[str]],
    start_marker: str,
    end_marker: str,
) -> str:
    table_class = DAILY_ENTRY_TABLE_CLASS if start_marker == DAILY_TABLE_START else ENTRY_TABLE_CLASS
    header = "".join(f"<th>{escape(title)}</th>" for title, _ in columns)
    body_rows = "".join(_render_html_row(row) for row in rows)
    return "\n".join(
        [
            start_marker,
            f'<table class="{table_class}">',
            f"<thead><tr>{header}</tr></thead>",
            f"<tbody>{body_rows}</tbody>",
            "</table>",
            end_marker,
            "",
        ]
    )


def _render_html_row(cells: list[str]) -> str:
    rendered_cells = "".join(f"<td>{_cell_html(cell)}</td>" for cell in cells)
    return f"<tr>{rendered_cells}</tr>"


def _cell_html(value: str) -> str:
    escaped = escape(value, quote=False)
    escaped = escaped.replace("&lt;br&gt;", "<br>")
    escaped = re.sub(r"&lt;(span[^&]*)&gt;", r"<\1>", escaped)
    escaped = escaped.replace("&lt;/span&gt;", "</span>")
    return escaped or "-"


def _split_title(previous: str, symbol: str) -> tuple[str, str]:
    lines = previous.splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0], "\n".join(lines[1:]).strip()
    return f"# {symbol} 开仓检查记录", previous.strip()


def _split_daily_trigger_title(previous: str) -> tuple[str, str]:
    lines = previous.splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0], "\n".join(lines[1:]).strip()
    return DAILY_ENTRY_TITLE, previous.strip()


def _extract_rows(content: str, expected_cells: int, start_marker: str, end_marker: str) -> list[list[str]]:
    html_rows = _extract_html_rows(content, expected_cells, start_marker, end_marker)
    if html_rows:
        return html_rows
    return _extract_markdown_rows(content, expected_cells)


def _extract_html_rows(content: str, expected_cells: int, start_marker: str, end_marker: str) -> list[list[str]]:
    if start_marker not in content or end_marker not in content:
        return []
    section = _extract_marked_section(content, start_marker, end_marker)
    rows: list[list[str]] = []
    for row_match in re.finditer(r"<tr>(.*?)</tr>", section, flags=re.DOTALL):
        cells = [
            _strip_tags(cell_match.group(1))
            for cell_match in re.finditer(r"<td[^>]*>(.*?)</td>", row_match.group(1), flags=re.DOTALL)
        ]
        if len(cells) == expected_cells:
            rows.append(cells)
    return rows


def _extract_markdown_rows(content: str, expected_cells: int) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if _looks_like_table_row(stripped):
            cells = _split_markdown_row(stripped)
            if len(cells) == expected_cells:
                rows.append(cells)
    return rows


def _split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _looks_like_table_row(line: str) -> bool:
    return bool(re.match(r"^\| (?:<span[^>]*>)?\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", line))


def _remove_latest_zone_section(content: str) -> str:
    if LATEST_ZONES_START not in content or LATEST_ZONES_END not in content:
        return content.strip()
    before, _, rest = content.partition(LATEST_ZONES_START)
    _, _, after = rest.partition(LATEST_ZONES_END)
    return f"{before.strip()}\n{after.strip()}".strip()


def _extract_marked_section(content: str, start_marker: str, end_marker: str) -> str:
    _, _, rest = content.partition(start_marker)
    section, _, _ = rest.partition(end_marker)
    return section


def _remove_marked_section(content: str, start_marker: str, end_marker: str) -> str:
    if start_marker not in content or end_marker not in content:
        return content
    before, _, rest = content.partition(start_marker)
    _, _, after = rest.partition(end_marker)
    return f"{before.rstrip()}\n{after.lstrip()}".strip()


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


def _should_skip_duplicate_static_row(existing_rows: list[list[str]], new_row: list[str]) -> bool:
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


def _is_static_provider_row(row: list[str]) -> bool:
    row_text = " | ".join(row)
    marker_hits = sum(1 for marker in STATIC_PROVIDER_NOTICE_MARKERS if marker in row_text)
    return marker_hits >= 2


def _extract_row_timestamp(row: list[str]) -> datetime | None:
    row_text = " | ".join(row)
    match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", row_text)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _route_model_text(decision: EntryDecision) -> str:
    route_label = {
        "standard_entry": "标准开仓",
        "probe_entry": "轻仓试错",
        "t_reentry": "T仓回补",
        "reject_reentry": "禁止回补",
    }.get(decision.entry_route, decision.entry_route)
    return f"{route_label} / {decision.entry_model}"


def _strip_tags(value: str) -> str:
    value = value.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    return re.sub(r"<[^>]+>", "", value).strip()


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def _resolve_entry_reference_price(decision: EntryDecision | None, daily_bars: list[Bar]) -> float | None:
    if decision is not None:
        if decision.current_price is not None:
            return decision.current_price
        if decision.planned_entry_price is not None:
            return decision.planned_entry_price
    if daily_bars:
        return daily_bars[-1].close
    return None


def _format_focus_zone_block(zones: list[PriceZone], reference_price: float | None) -> str:
    support = _select_focus_zone(zones, reference_price, zone_type="support")
    resistance = _select_focus_zone(zones, reference_price, zone_type="resistance")
    if support is None and resistance is None:
        return ""
    lines = ["> [!tip] 当前最需要关注的支撑/压力位"]
    if support is not None:
        lines.append(f"> - 支撑位：{_describe_zone(support, reference_price)}")
    if resistance is not None:
        lines.append(f"> - 压力位：{_describe_zone(resistance, reference_price)}")
    return "\n".join(lines)


def _select_focus_zone(
    zones: list[PriceZone],
    reference_price: float | None,
    zone_type: str,
) -> PriceZone | None:
    candidates = [zone for zone in zones if zone_type in zone.tags]
    if not candidates:
        return None
    if reference_price is None:
        return sorted(
            candidates,
            key=lambda zone: (
                _level_rank(zone.level),
                zone.importance_score,
                zone.score,
            ),
            reverse=True,
        )[0]
    return sorted(
        candidates,
        key=lambda zone: (
            _zone_position_rank(zone, reference_price, zone_type),
            _zone_distance(zone, reference_price),
            -_level_rank(zone.level),
            -zone.importance_score,
            -zone.score,
        ),
    )[0]


def _zone_position_rank(zone: PriceZone, reference_price: float, zone_type: str) -> int:
    if zone.contains(reference_price):
        return 0
    if zone_type == "support":
        return 1 if zone.high <= reference_price else 2
    return 1 if zone.low >= reference_price else 2


def _zone_distance(zone: PriceZone, reference_price: float) -> float:
    if zone.contains(reference_price):
        return 0.0
    if reference_price < zone.low:
        return zone.low - reference_price
    return reference_price - zone.high


def _level_rank(level) -> int:
    return {"A": 4, "B": 3, "C": 2, "D": 1}.get(str(level), 0)


def _describe_zone(zone: PriceZone, reference_price: float | None) -> str:
    timeframe = {"1d": "日线", "1w": "周线", "15m": "15分钟", "60m": "60分钟"}.get(zone.timeframe, zone.timeframe)
    zone_type = "支撑区" if "support" in zone.tags else "压力区"
    base = f"{timeframe}{zone.level}级{zone_type} {zone.low:.2f}-{zone.high:.2f}"
    if reference_price is None:
        return base
    if zone.contains(reference_price):
        return f"{base}（当前位于区间内）"
    distance_pct = _zone_distance(zone, reference_price) / reference_price * 100 if reference_price else 0.0
    return f"{base}（距当前价约 {distance_pct:.2f}%）"


def _safe_filename(value: str) -> str:
    return "".join(ch for ch in value.strip() if ch.isalnum() or ch in {"_", "-", "."}) or "unknown"


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


def _split_title(previous: str, symbol: str) -> tuple[str, str]:
    previous = _strip_frontmatter(previous)
    lines = previous.splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0], "\n".join(lines[1:]).strip()
    return f"# {symbol} 开仓检查记录", previous.strip()


def _split_daily_trigger_title(previous: str) -> tuple[str, str]:
    previous = _strip_frontmatter(previous)
    lines = previous.splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0], "\n".join(lines[1:]).strip()
    return DAILY_ENTRY_TITLE, previous.strip()


def _prepend_entry_run(
    previous: str,
    row_cells: list[str],
    symbol: str,
    chart_ref: str,
    zones: list[PriceZone],
    reference_price: float | None,
) -> str:
    title, body = _split_title(previous, symbol)
    body = _remove_latest_zone_section(body)
    existing_rows = _extract_rows(body, expected_cells=len(ENTRY_COLUMNS), start_marker=ENTRY_TABLE_START, end_marker=ENTRY_TABLE_END)
    if _should_skip_duplicate_static_row(existing_rows, row_cells):
        rows = existing_rows
    else:
        rows = [row_cells, *existing_rows]
    focus_block = _format_focus_zone_block(zones, reference_price)
    zone_section = "\n".join(
        [
            LATEST_ZONES_START,
            *([focus_block, ""] if focus_block else []),
            f'<img src="{chart_ref}" alt="{symbol} 最新支撑压力图" style="width: 40%; max-width: 40%;" />',
            "",
            LATEST_ZONES_END,
            "",
            "",
        ]
    )
    table = _render_table(ENTRY_COLUMNS, rows, ENTRY_TABLE_START, ENTRY_TABLE_END)
    return _compose_document(title, f"{zone_section}{table}".rstrip())


def _write_daily_allowed_summary(monitor_dir: Path, decisions: list[EntryDecision], now: datetime) -> None:
    allowed = [decision for decision in decisions if decision.allowed]
    if not allowed:
        return
    path = monitor_dir / "当日可开仓候选.md"
    previous = path.read_text(encoding="utf-8") if path.exists() else _compose_document(DAILY_ENTRY_TITLE, "")
    rows = []
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    for decision in allowed:
        display_value = normalize_symbol_name(decision.symbol, decision.symbol_name) or decision.symbol
        rows.append(
            [
                f'<span class="trade-monitor-alert-time">{now_text}</span>',
                display_value,
                _route_model_text(decision),
                str(decision.entry_score),
                _fmt(decision.planned_entry_price),
                _fmt(decision.stop_loss_price),
                _fmt(decision.first_take_profit_price),
                _fmt(decision.risk_reward_ratio),
                "；".join(decision.reasons),
            ]
        )
    existing_rows = _extract_rows(previous, expected_cells=len(DAILY_ENTRY_COLUMNS), start_marker=DAILY_TABLE_START, end_marker=DAILY_TABLE_END)
    body = _remove_marked_section(previous, DAILY_TABLE_START, DAILY_TABLE_END).strip()
    title, _ = _split_daily_trigger_title(body)
    table = _render_table(DAILY_ENTRY_COLUMNS, rows + existing_rows, DAILY_TABLE_START, DAILY_TABLE_END)
    path.write_text(_compose_document(title, table.rstrip()), encoding="utf-8")
