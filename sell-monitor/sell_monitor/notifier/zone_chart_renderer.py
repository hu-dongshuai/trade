from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import Bar, PriceZone


WIDTH = 1200
HEIGHT = 620
LEFT_PAD = 70
RIGHT_PAD = 110
TOP_PAD = 34
BOTTOM_PAD = 56
MAX_WEEKS = 80


def render_weekly_zone_chart(
    output_dir: Path,
    symbol: str,
    daily_bars: list[Bar],
    zones: list[PriceZone],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{_safe_filename(symbol)}_latest_zones.svg"
    weekly_bars = _to_weekly_bars(daily_bars)[-MAX_WEEKS:]
    svg = _build_svg(symbol, weekly_bars, zones)
    path.write_text(svg, encoding="utf-8")
    return path


def _build_svg(symbol: str, weekly_bars: list[Bar], zones: list[PriceZone]) -> str:
    plot_width = WIDTH - LEFT_PAD - RIGHT_PAD
    plot_height = HEIGHT - TOP_PAD - BOTTOM_PAD
    price_low, price_high = _price_bounds(weekly_bars, zones)

    def x_for(index: int) -> float:
        if len(weekly_bars) <= 1:
            return LEFT_PAD + plot_width / 2
        return LEFT_PAD + index * (plot_width / (len(weekly_bars) - 1))

    def y_for(price: float) -> float:
        span = max(price_high - price_low, 1e-9)
        return TOP_PAD + (price_high - price) / span * plot_height

    candle_step = plot_width / max(len(weekly_bars), 1)
    candle_width = max(4, min(12, candle_step * 0.56))
    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="#151515"/>',
        f'<text x="{LEFT_PAD}" y="24" fill="#e6e6e6" font-size="18" font-family="Arial">{_escape(symbol)} 周线支撑压力图</text>',
        f'<rect x="{LEFT_PAD}" y="{TOP_PAD}" width="{plot_width}" height="{plot_height}" fill="#1d1d1d" stroke="#363636"/>',
    ]

    for idx in range(5):
        y = TOP_PAD + idx * plot_height / 4
        price = price_high - idx * (price_high - price_low) / 4
        lines.append(f'<line x1="{LEFT_PAD}" y1="{y:.2f}" x2="{LEFT_PAD + plot_width}" y2="{y:.2f}" stroke="#2b2b2b"/>')
        lines.append(
            f'<text x="{LEFT_PAD + plot_width + 10}" y="{y + 4:.2f}" fill="#a8a8a8" font-size="12" font-family="Arial">{price:.2f}</text>'
        )

    for zone in zones:
        if "support" not in zone.tags and "resistance" not in zone.tags:
            continue
        low_y = y_for(zone.low)
        high_y = y_for(zone.high)
        rect_y = min(low_y, high_y)
        rect_h = max(abs(low_y - high_y), 3)
        color = _zone_color(zone)
        opacity = _zone_opacity(zone.level)
        lines.append(
            f'<rect x="{LEFT_PAD}" y="{rect_y:.2f}" width="{plot_width}" height="{rect_h:.2f}" fill="{color}" opacity="{opacity:.2f}"/>'
        )
        label = f'{zone.level.value} {zone.low:.2f}-{zone.high:.2f}'
        lines.append(
            f'<text x="{LEFT_PAD + plot_width - 5}" y="{rect_y + 14:.2f}" text-anchor="end" fill="{color}" font-size="12" font-family="Arial">{_escape(label)}</text>'
        )

    for idx, bar in enumerate(weekly_bars):
        x = x_for(idx)
        open_y = y_for(bar.open)
        close_y = y_for(bar.close)
        high_y = y_for(bar.high)
        low_y = y_for(bar.low)
        up = bar.close >= bar.open
        color = "#d95858" if up else "#4ca36a"
        body_y = min(open_y, close_y)
        body_h = max(abs(close_y - open_y), 2)
        lines.append(f'<line x1="{x:.2f}" y1="{high_y:.2f}" x2="{x:.2f}" y2="{low_y:.2f}" stroke="{color}" stroke-width="1.4"/>')
        lines.append(
            f'<rect x="{x - candle_width / 2:.2f}" y="{body_y:.2f}" width="{candle_width:.2f}" height="{body_h:.2f}" fill="{color}" opacity="0.78"/>'
        )

    if weekly_bars:
        first = weekly_bars[0].ts.strftime("%Y-%m")
        last = weekly_bars[-1].ts.strftime("%Y-%m")
        lines.append(f'<text x="{LEFT_PAD}" y="{HEIGHT - 22}" fill="#a8a8a8" font-size="12" font-family="Arial">{first}</text>')
        lines.append(
            f'<text x="{LEFT_PAD + plot_width}" y="{HEIGHT - 22}" text-anchor="end" fill="#a8a8a8" font-size="12" font-family="Arial">{last}</text>'
        )
    else:
        lines.append(
            f'<text x="{WIDTH / 2}" y="{HEIGHT / 2}" text-anchor="middle" fill="#bfbfbf" font-size="18" font-family="Arial">暂无周线K线数据</text>'
        )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _price_bounds(weekly_bars: list[Bar], zones: list[PriceZone]) -> tuple[float, float]:
    values: list[float] = []
    for bar in weekly_bars:
        values.extend([bar.low, bar.high])
    for zone in zones:
        values.extend([zone.low, zone.high])
    if not values:
        return 0.0, 1.0
    low = min(values)
    high = max(values)
    pad = max((high - low) * 0.08, high * 0.01 if high else 1.0)
    return max(0.0, low - pad), high + pad


def _zone_color(zone: PriceZone) -> str:
    if "support" in zone.tags and "resistance" not in zone.tags:
        return "#21b36b"
    if "resistance" in zone.tags and "support" not in zone.tags:
        return "#e34b4b"
    return "#d6b44c"


def _zone_opacity(level: ZoneLevel) -> float:
    if level == ZoneLevel.A:
        return 0.34
    if level == ZoneLevel.B:
        return 0.24
    if level == ZoneLevel.C:
        return 0.16
    return 0.08


def _to_weekly_bars(daily_bars: list[Bar]) -> list[Bar]:
    if not daily_bars:
        return []
    groups: dict[tuple[int, int], list[Bar]] = {}
    for bar in daily_bars:
        iso = bar.ts.isocalendar()
        groups.setdefault((iso.year, iso.week), []).append(bar)

    weekly: list[Bar] = []
    for _, bars in sorted(groups.items()):
        ordered = sorted(bars, key=lambda item: item.ts)
        first = ordered[0]
        last = ordered[-1]
        weekly.append(
            Bar(
                ts=datetime(last.ts.year, last.ts.month, last.ts.day),
                open=first.open,
                high=max(bar.high for bar in ordered),
                low=min(bar.low for bar in ordered),
                close=last.close,
                volume=sum(bar.volume for bar in ordered),
            )
        )
    return weekly


def _safe_filename(value: str) -> str:
    return "".join(ch for ch in value.strip() if ch.isalnum() or ch in {"_", "-", "."}) or "unknown"


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
