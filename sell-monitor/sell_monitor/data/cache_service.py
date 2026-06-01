from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import Bar, FundamentalSnapshot, PriceZone, Quote


DAILY_ZONE_CACHE_VERSION = 4


class FileMarketDataCache:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def load_quote(self, symbol: str, max_age_seconds: int | None = None) -> Quote | None:
        payload = self._load_json(self._quote_path(symbol))
        if not payload:
            return None
        if max_age_seconds is not None and self._is_stale(payload, max_age_seconds):
            return None
        return Quote(
            symbol=str(payload["symbol"]),
            price=float(payload["price"]),
            ts=datetime.fromisoformat(str(payload["ts"])),
        )

    def save_quote(self, quote: Quote) -> None:
        self._save_json(
            self._quote_path(quote.symbol),
            {
                "saved_at": datetime.now().isoformat(),
                "symbol": quote.symbol,
                "price": quote.price,
                "ts": quote.ts.isoformat(),
            },
        )

    def load_fundamental_snapshot(
        self,
        symbol: str,
        max_age_seconds: int | None = None,
        end_dt: datetime | None = None,
    ) -> FundamentalSnapshot | None:
        payload = self._load_json(self._fundamental_path(symbol))
        if not payload:
            return None
        if max_age_seconds is not None and self._is_stale(payload, max_age_seconds):
            return None
        report_date_raw = payload.get("report_date")
        snapshot = FundamentalSnapshot(
            symbol=str(payload["symbol"]),
            ts=datetime.fromisoformat(str(payload["ts"])),
            report_date=(datetime.fromisoformat(str(report_date_raw)) if report_date_raw else None),
            revenue_yoy=_optional_float(payload.get("revenue_yoy")),
            previous_revenue_yoy=_optional_float(payload.get("previous_revenue_yoy")),
            net_profit_yoy=_optional_float(payload.get("net_profit_yoy")),
            deducted_net_profit_yoy=_optional_float(payload.get("deducted_net_profit_yoy")),
            previous_deducted_net_profit_yoy=_optional_float(payload.get("previous_deducted_net_profit_yoy")),
            gross_margin=_optional_float(payload.get("gross_margin")),
            previous_gross_margin=_optional_float(payload.get("previous_gross_margin")),
            net_margin=_optional_float(payload.get("net_margin")),
            previous_net_margin=_optional_float(payload.get("previous_net_margin")),
            roe=_optional_float(payload.get("roe")),
            operating_cashflow_to_profit=_optional_float(payload.get("operating_cashflow_to_profit")),
            debt_asset_ratio=_optional_float(payload.get("debt_asset_ratio")),
            pe_percentile=_optional_float(payload.get("pe_percentile")),
            event_risk=bool(payload.get("event_risk", False)),
            event_note=(str(payload["event_note"]) if payload.get("event_note") else None),
        )
        if end_dt is not None and snapshot.report_date is not None and snapshot.report_date > end_dt:
            return None
        return snapshot

    def save_fundamental_snapshot(self, snapshot: FundamentalSnapshot) -> None:
        self._save_json(
            self._fundamental_path(snapshot.symbol),
            {
                "saved_at": datetime.now().isoformat(),
                "symbol": snapshot.symbol,
                "ts": snapshot.ts.isoformat(),
                "report_date": snapshot.report_date.isoformat() if snapshot.report_date else None,
                "revenue_yoy": snapshot.revenue_yoy,
                "previous_revenue_yoy": snapshot.previous_revenue_yoy,
                "net_profit_yoy": snapshot.net_profit_yoy,
                "deducted_net_profit_yoy": snapshot.deducted_net_profit_yoy,
                "previous_deducted_net_profit_yoy": snapshot.previous_deducted_net_profit_yoy,
                "gross_margin": snapshot.gross_margin,
                "previous_gross_margin": snapshot.previous_gross_margin,
                "net_margin": snapshot.net_margin,
                "previous_net_margin": snapshot.previous_net_margin,
                "roe": snapshot.roe,
                "operating_cashflow_to_profit": snapshot.operating_cashflow_to_profit,
                "debt_asset_ratio": snapshot.debt_asset_ratio,
                "pe_percentile": snapshot.pe_percentile,
                "event_risk": snapshot.event_risk,
                "event_note": snapshot.event_note,
            },
        )

    def load_bars(self, symbol: str, timeframe: str, max_age_seconds: int | None = None) -> list[Bar] | None:
        payload = self._load_json(self._bars_path(symbol, timeframe))
        if not payload:
            return None
        if max_age_seconds is not None and self._is_stale(payload, max_age_seconds):
            return None
        if not payload.get("bars"):
            return None
        return [
            Bar(
                ts=datetime.fromisoformat(str(item["ts"])),
                open=float(item["open"]),
                high=float(item["high"]),
                low=float(item["low"]),
                close=float(item["close"]),
                volume=float(item["volume"]),
            )
            for item in payload["bars"]
        ]

    def save_bars(self, symbol: str, timeframe: str, bars: list[Bar]) -> None:
        self._write_bars(symbol, timeframe, bars)

    def merge_save_bars(self, symbol: str, timeframe: str, bars: list[Bar]) -> None:
        merged = _merge_bars(self.load_bars(symbol, timeframe) or [], bars)
        self._write_bars(symbol, timeframe, merged)

    def _write_bars(self, symbol: str, timeframe: str, bars: list[Bar]) -> None:
        self._save_json(
            self._bars_path(symbol, timeframe),
            {
                "saved_at": datetime.now().isoformat(),
                "symbol": symbol,
                "timeframe": timeframe,
                "bars": [
                    {
                        "ts": bar.ts.isoformat(),
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume,
                    }
                    for bar in bars
                ],
            },
        )

    def load_state(self, key: str, max_age_seconds: int | None = None) -> str | None:
        payload = self._load_json(self._state_path(key))
        if not payload:
            return None
        if max_age_seconds is not None and self._is_stale(payload, max_age_seconds):
            return None
        return str(payload["value"])

    def save_state(self, key: str, value: str) -> None:
        self._save_json(self._state_path(key), {"saved_at": datetime.now().isoformat(), "value": value})

    def load_daily_zone_bundle(self, symbol: str, latest_daily_ts: datetime) -> dict | None:
        payload = self._load_json(self._daily_zone_path(symbol))
        if not payload:
            return None
        if str(payload.get("latest_daily_ts")) != latest_daily_ts.isoformat():
            return None
        if int(payload.get("strategy_version", 0)) != DAILY_ZONE_CACHE_VERSION:
            return None
        zones = [
            PriceZone(
                name=str(item["name"]),
                timeframe=str(item["timeframe"]),
                low=float(item["low"]),
                high=float(item["high"]),
                score=int(item["score"]),
                level=ZoneLevel(str(item["level"])),
                tags=list(item.get("tags", [])),
                touches=int(item.get("touches", 0)),
                importance_score=int(item.get("importance_score", item.get("score", 0))),
                fragility_score=int(item.get("fragility_score", 0)),
                invalidation_price=(
                    float(item["invalidation_price"]) if item.get("invalidation_price") is not None else None
                ),
            )
            for item in payload["zones"]
        ]
        return {
            "zones": zones,
            "daily_trend": str(payload["daily_trend"]),
        }

    def save_daily_zone_bundle(
        self,
        symbol: str,
        latest_daily_ts: datetime,
        zones: list[PriceZone],
        daily_trend: str,
    ) -> None:
        self._save_json(
            self._daily_zone_path(symbol),
            {
                "saved_at": datetime.now().isoformat(),
                "symbol": symbol,
                "strategy_version": DAILY_ZONE_CACHE_VERSION,
                "latest_daily_ts": latest_daily_ts.isoformat(),
                "daily_trend": daily_trend,
                "zones": [
                    {
                        "name": zone.name,
                        "timeframe": zone.timeframe,
                        "low": zone.low,
                        "high": zone.high,
                        "score": zone.score,
                        "level": zone.level.value,
                        "tags": zone.tags,
                        "touches": zone.touches,
                        "importance_score": zone.importance_score,
                        "fragility_score": zone.fragility_score,
                        "invalidation_price": zone.invalidation_price,
                    }
                    for zone in zones
                ],
            },
        )
        self._save_daily_zone_markdown(symbol, latest_daily_ts, zones, daily_trend)

    def _quote_path(self, symbol: str) -> Path:
        return self.base_dir / f"{symbol}_quote.json"

    def _fundamental_path(self, symbol: str) -> Path:
        return self.base_dir / f"{symbol}_fundamental.json"

    def _bars_path(self, symbol: str, timeframe: str) -> Path:
        return self.base_dir / f"{symbol}_{timeframe}.json"

    def _state_path(self, key: str) -> Path:
        return self.base_dir / f"state_{key}.json"

    def _daily_zone_path(self, symbol: str) -> Path:
        return self.base_dir / f"{symbol}_daily_zones.json"

    def _daily_zone_markdown_path(self, symbol: str) -> Path:
        export_dir = self.base_dir / "key_levels"
        export_dir.mkdir(parents=True, exist_ok=True)
        return export_dir / f"{symbol}_daily_key_levels.md"

    def daily_zone_markdown_path(self, symbol: str) -> Path:
        return self._daily_zone_markdown_path(symbol)

    def export_replay_daily_zone_markdown(
        self,
        symbol: str,
        snapshot_key: str,
        latest_daily_ts: datetime,
        zones: list[PriceZone],
        daily_trend: str,
    ) -> Path:
        export_dir = self.base_dir / "key_levels" / "replay"
        export_dir.mkdir(parents=True, exist_ok=True)
        path = export_dir / f"{symbol}_{snapshot_key}_daily_key_levels.md"
        self._write_daily_zone_markdown(path, symbol, latest_daily_ts, zones, daily_trend)
        return path

    def _load_json(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_json(self, path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _is_stale(self, payload: dict, max_age_seconds: int) -> bool:
        saved_at_raw = payload.get("saved_at")
        if not saved_at_raw:
            return True
        saved_at = datetime.fromisoformat(str(saved_at_raw))
        return datetime.now() - saved_at > timedelta(seconds=max_age_seconds)

    def _save_daily_zone_markdown(
        self,
        symbol: str,
        latest_daily_ts: datetime,
        zones: list[PriceZone],
        daily_trend: str,
    ) -> None:
        self._write_daily_zone_markdown(self._daily_zone_markdown_path(symbol), symbol, latest_daily_ts, zones, daily_trend)

    def _write_daily_zone_markdown(
        self,
        path: Path,
        symbol: str,
        latest_daily_ts: datetime,
        zones: list[PriceZone],
        daily_trend: str,
    ) -> None:
        lines = [
            f"# {symbol} 日线关键价位",
            "",
            f"- 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 对应最新日线: {latest_daily_ts.strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 日线趋势: {daily_trend}",
            "",
            "| 周期 | 等级 | 名称 | 区间下沿 | 区间上沿 | 净分 | 重要性 | 脆弱性 | 失效价 | 触达次数 | 标签 |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for zone in zones:
            invalidation = f"{zone.invalidation_price:.2f}" if zone.invalidation_price is not None else "-"
            lines.append(
                f"| {zone.timeframe} | {zone.level.value} | {zone.name} | {zone.low:.2f} | {zone.high:.2f} | "
                f"{zone.score} | {zone.importance_score} | {zone.fragility_score} | {invalidation} | "
                f"{zone.touches} | {', '.join(zone.tags)} |"
            )
        if not zones:
            lines.append("| - | - | 无有效关键价位 | - | - | - | - | - | - | - | - |")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _merge_bars(existing: list[Bar], incoming: list[Bar]) -> list[Bar]:
    by_ts = {bar.ts: bar for bar in existing}
    by_ts.update({bar.ts: bar for bar in incoming})
    return [by_ts[ts] for ts in sorted(by_ts)]


def _optional_float(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
