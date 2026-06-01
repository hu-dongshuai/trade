from __future__ import annotations

import argparse
import sys
from datetime import datetime

from sell_monitor.data.baostock_provider import BaostockMarketDataProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnose BaoStock historical minute data availability.")
    parser.add_argument("--symbol", required=True, help="A-share symbol, for example 002241.")
    parser.add_argument("--start-date", required=True, help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", required=True, help="End date in YYYY-MM-DD format.")
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    start_dt = datetime.strptime(args.start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(args.end_date, "%Y-%m-%d").replace(hour=15)
    try:
        provider = BaostockMarketDataProvider()
        bars = provider.get_m15_bars_until(args.symbol, end_dt, limit=5000)
        bars = [bar for bar in bars if bar.ts >= start_dt]
    except Exception as exc:
        print(f"[{args.symbol}] BaoStock 诊断失败：{exc}")
        return 1
    finally:
        if "provider" in locals():
            provider.close()

    if not bars:
        print(f"[{args.symbol}] BaoStock 在 {args.start_date} 至 {args.end_date} 没有返回15分钟数据")
        return 1
    print(f"[{args.symbol}] BaoStock 15分钟数据可用")
    print(f"bars: {len(bars)}")
    print(f"earliest: {bars[0].ts.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"latest: {bars[-1].ts.strftime('%Y-%m-%d %H:%M:%S')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
