from __future__ import annotations

from sell_monitor.data.market_data_provider import MarketDataProvider
from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import DailyContext, PriceZone
from sell_monitor.indicators.atr import compute_atr
from sell_monitor.indicators.ma import closing_ma
from sell_monitor.zones.activation_gate import find_active_zone
from sell_monitor.zones.daily_fibonacci_detector import detect_daily_fibonacci_resistance_zones
from sell_monitor.zones.daily_fvg_detector import detect_daily_fvg
from sell_monitor.zones.daily_liquidity_detector import detect_daily_liquidity_zones
from sell_monitor.zones.daily_order_block_detector import detect_daily_order_blocks
from sell_monitor.zones.daily_sr_detector import detect_daily_sr_zones
from sell_monitor.zones.daily_zone_filter import filter_current_daily_zones, is_congestion_zone, is_hidden_display_zone, prepare_daily_zones
from sell_monitor.zones.daily_zone_ranker import rank_daily_zones
from sell_monitor.zones.weekly_resistance_detector import detect_weekly_resistance_zones


def _infer_daily_trend(daily_bars) -> str:
    if len(daily_bars) < 20:
        return "neutral"
    ma20 = closing_ma(daily_bars, 20)
    last_close = daily_bars[-1].close
    return "up" if last_close >= ma20 else "down"


def build_daily_context_from_data(
    symbol: str,
    current_price: float,
    daily_bars,
    market_state: str = "neutral",
    sector_state: str = "neutral",
    cache=None,
    cache_key: str | None = None,
    notices: list[str] | None = None,
) -> DailyContext:
    daily_trend = _infer_daily_trend(daily_bars)
    daily_atr = compute_atr(daily_bars, 14)
    zone_bundle = None
    if cache and cache_key and daily_bars:
        zone_bundle = cache.load_daily_zone_bundle(cache_key, daily_bars[-1].ts)
    if zone_bundle:
        zones = zone_bundle["zones"]
        daily_trend = zone_bundle["daily_trend"]
        if notices is not None:
            notices.append(f"[{symbol}] 已命中本地缓存日线关键价位")
    else:
        sr = detect_daily_sr_zones(daily_bars)
        fvg = detect_daily_fvg(daily_bars)
        liquidity = detect_daily_liquidity_zones(daily_bars)
        order_blocks = detect_daily_order_blocks(daily_bars)
        weekly_resistance = detect_weekly_resistance_zones(daily_bars)
        fibonacci = detect_daily_fibonacci_resistance_zones(daily_bars)
        zones = prepare_daily_zones(
            rank_daily_zones(sr, fvg, liquidity, order_blocks, weekly_resistance, fibonacci),
            daily_bars,
            daily_atr,
        )
        if cache and cache_key and daily_bars:
            cache.save_daily_zone_bundle(cache_key, daily_bars[-1].ts, zones, daily_trend)
            if notices is not None:
                notices.append(f"[{symbol}] 日线关键价位已导出到 {cache.daily_zone_markdown_path(cache_key)}")
    zones = _daily_active_zones(filter_current_daily_zones(zones, current_price))
    active_zone = find_active_zone(current_price, daily_atr, zones)
    return DailyContext(
        symbol=symbol,
        current_price=current_price,
        daily_zones=zones,
        active_zone=active_zone,
        daily_trend=daily_trend,
        market_state=market_state,
        sector_state=sector_state,
        daily_bars=list(daily_bars),
    )


def _daily_active_zones(zones: list[PriceZone]) -> list[PriceZone]:
    return [
        zone
        for zone in zones
        if not is_hidden_display_zone(zone)
        and not is_congestion_zone(zone)
        if zone.level in {ZoneLevel.A, ZoneLevel.B}
        or (zone.level == ZoneLevel.C and "resistance" in zone.tags)
    ]


def _daily_ab_zones(zones: list[PriceZone]) -> list[PriceZone]:
    return _daily_active_zones(zones)


def build_daily_context(provider: MarketDataProvider, symbol: str) -> DailyContext:
    quote = provider.get_latest_quote(symbol)
    daily_bars = provider.get_daily_bars(symbol, limit=200)
    cache = getattr(provider, "cache", None)
    notices = getattr(provider, "_notices", None)
    return build_daily_context_from_data(
        symbol=symbol,
        current_price=quote.price,
        daily_bars=daily_bars,
        market_state=provider.get_market_state(),
        sector_state=provider.get_sector_state(symbol),
        cache=cache,
        cache_key=symbol,
        notices=notices,
    )
