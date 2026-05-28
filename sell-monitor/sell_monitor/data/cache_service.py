from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import Bar, PriceZone, Quote


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
                    }
                    for zone in zones
                ],
            },
        )
        self._save_daily_zone_markdown(symbol, latest_daily_ts, zones, daily_trend)

    def _quote_path(self, symbol: str) -> Path:
        return self.base_dir / f"{symbol}_quote.json"

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
            "| 等级 | 名称 | 区间下沿 | 区间上沿 | 分数 | 标签 | 触达次数 |",
            "| --- | --- | ---: | ---: | ---: | --- | ---: |",
        ]
        for zone in zones:
            lines.append(
                f"| {zone.level.value} | {zone.name} | {zone.low:.2f} | {zone.high:.2f} | "
                f"{zone.score} | {', '.join(zone.tags)} | {zone.touches} |"
            )
        if not zones:
            lines.append("| - | 无有效关键价位 | - | - | - | - | - |")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
