from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sell_monitor.config import ObsidianMonitorConfig
from sell_monitor.domain.enums import Action
from sell_monitor.domain.models import Decision
from sell_monitor.notifier.alert_formatter import format_decision


SELL_SIGNAL_ACTIONS = {Action.REDUCE, Action.STOP_LOSS, Action.EXIT_ALL}


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

    def write_run(self, symbols: list[str], decisions: list[Decision], notices: list[str]) -> None:
        self.monitor_dir.mkdir(parents=True, exist_ok=True)
        decisions_by_symbol = {decision.symbol: decision for decision in decisions}
        notices_by_symbol = _group_notices_by_symbol(notices)
        now = datetime.now()

        for symbol in symbols:
            safe_symbol = _safe_filename(symbol)
            path = self.monitor_dir / f"{safe_symbol}.md"
            previous = path.read_text(encoding="utf-8") if path.exists() else _initial_content(safe_symbol)
            entry = _format_run_entry(
                symbol=safe_symbol,
                decision=decisions_by_symbol.get(symbol),
                notices=notices_by_symbol.get(symbol, []),
                now=now,
            )
            path.write_text(_prepend_entry(previous, entry), encoding="utf-8")
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


def _format_run_entry(symbol: str, decision: Decision | None, notices: list[str], now: datetime) -> str:
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    has_sell_signal = decision is not None and decision.action in SELL_SIGNAL_ACTIONS
    time_cell = _format_time_cell(now_text, has_sell_signal)
    action = decision.action.value if decision else "none"
    score = str(decision.total_score) if decision else "0"
    priority = decision.priority.value if decision else "normal"
    conclusion = "卖出信号" if has_sell_signal else "未触发卖出信号"
    reason = _summarize_reasons(decision, notices)
    next_step = decision.next_step if decision else "继续观察"
    cancel_condition = decision.cancel_condition if decision else "-"
    rows = [
        "## 监控记录",
        "",
        "| 检测时间 | 股票代码 | 结论 | 动作 | 分数 | 优先级 | 原因/提示 | 下一步 | 取消条件 |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
        (
            f"| {time_cell} | {symbol} | {conclusion} | {action} | {score} | {priority} | "
            f"{_table_cell(reason)} | {_table_cell(next_step)} | {_table_cell(cancel_condition)} |"
        ),
        "",
    ]
    if decision:
        rows.extend(["```text", format_decision(decision), "```", ""])
    return "\n".join(rows)


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
    date_text = now.strftime("%Y-%m-%d")
    lines = [
        f"## {date_text} {now_text}",
        "",
        "| 时间 | 股票代码 | 卖出动作 | 分数 | 优先级 | 原因 | 建议 |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for decision in decisions:
        lines.append(
            f"| {_format_time_cell(now_text, True)} | {decision.symbol} | {decision.action.value} | "
            f"{decision.total_score} | {decision.priority.value} | {_table_cell(_join_reasons(decision.reasons))} | "
            f"{_table_cell(decision.next_step)} |"
        )
    lines.append("")
    return "\n".join(lines)


def _summarize_reasons(decision: Decision | None, notices: list[str]) -> str:
    parts = []
    if decision:
        parts.extend(decision.reasons)
    parts.extend(notices)
    if not parts:
        return "本轮检测正常，无额外提示"
    return "；".join(parts)


def _join_reasons(reasons: list[str]) -> str:
    return "；".join(reasons) if reasons else "-"


def _table_cell(value: str) -> str:
    return value.replace("\r", " ").replace("\n", "<br>").replace("|", "\\|").strip() or "-"


def _prepend_entry(previous: str, entry: str) -> str:
    lines = previous.splitlines()
    if lines and lines[0].startswith("# "):
        title = lines[0]
        body = "\n".join(lines[1:]).strip()
        return f"{title}\n\n{entry}{body and body + chr(10)}"
    body = previous.strip()
    return f"{entry}{body and body + chr(10)}"
