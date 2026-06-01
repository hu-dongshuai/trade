from __future__ import annotations

from sell_monitor.domain.models import PriceZone


def format_zone_table(zones: list[PriceZone], symbol: str | None = None) -> list[str]:
    lines = [
        "### 支撑压力位",
        "",
        "| 股票 | 周期 | 等级 | 类型 | 区间下沿 | 区间上沿 | 净分 | 重要性 | 脆弱性 | 失效价 | 触达次数 | 标签 |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    if not zones:
        lines.append(f"| {symbol or '-'} | - | - | 无有效支撑压力位 | - | - | - | - | - | - | - | - |")
        lines.append("")
        return lines

    for zone in zones:
        zone_type = _zone_type(zone)
        invalidation = f"{zone.invalidation_price:.2f}" if zone.invalidation_price is not None else "-"
        lines.append(
            f"| {symbol or '-'} | {zone.timeframe} | {zone.level.value} | {zone_type} | "
            f"{zone.low:.2f} | {zone.high:.2f} | {zone.score} | {zone.importance_score} | "
            f"{zone.fragility_score} | {invalidation} | {zone.touches} | {_table_cell(', '.join(zone.tags))} |"
        )
    lines.append("")
    return lines


def format_multi_symbol_zone_tables(zone_snapshots: dict[str, list[PriceZone]]) -> list[str]:
    lines = ["## 支撑压力位", ""]
    if not zone_snapshots:
        lines.extend(["暂无可用支撑压力位。", ""])
        return lines
    for symbol in sorted(zone_snapshots):
        lines.extend(format_zone_table(zone_snapshots[symbol], symbol=symbol))
    return lines


def _zone_type(zone: PriceZone) -> str:
    has_support = "support" in zone.tags
    has_resistance = "resistance" in zone.tags
    if has_support and has_resistance:
        return "支撑/压力"
    if has_support:
        return "支撑"
    if has_resistance:
        return "压力"
    return "参考"


def _table_cell(value: str) -> str:
    return value.replace("\r", " ").replace("\n", "<br>").replace("|", "\\|").strip() or "-"
