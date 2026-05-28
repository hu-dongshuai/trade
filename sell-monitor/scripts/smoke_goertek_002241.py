from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sell_monitor.config import load_default_config
from sell_monitor.data.provider_factory import build_market_data_provider


def main() -> int:
    config = load_default_config(PROJECT_ROOT)
    provider = build_market_data_provider(config)
    symbol = "002241"
    result = {
        "symbol": symbol,
        "provider": config.provider,
    }
    try:
        quote = provider.get_latest_quote(symbol)
        result["quote_price"] = quote.price
        result["quote_ts"] = quote.ts.isoformat()
    except Exception as exc:
        result["quote_error"] = str(exc)
    try:
        daily_bars = provider.get_daily_bars(symbol, limit=30)
        result["daily_bar_count"] = len(daily_bars)
        result["daily_last_ts"] = daily_bars[-1].ts.isoformat() if daily_bars else None
    except Exception as exc:
        result["daily_error"] = str(exc)
    try:
        m15_bars = provider.get_m15_bars(symbol, limit=64)
        result["m15_bar_count"] = len(m15_bars)
        result["m15_last_ts"] = m15_bars[-1].ts.isoformat() if m15_bars else None
    except Exception as exc:
        result["m15_error"] = str(exc)
    try:
        result["market_state"] = provider.get_market_state()
    except Exception as exc:
        result["market_state_error"] = str(exc)
    try:
        result["sector_state"] = provider.get_sector_state(symbol)
    except Exception as exc:
        result["sector_state_error"] = str(exc)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
