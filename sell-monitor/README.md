# Sell Monitor

A local-first, rule-based A-share monitor project with two parallel capabilities:

- sell monitoring
- long-entry checking

The project follows a layered process:

1. Use daily and weekly bars to build and rank major key price zones.
2. Use 15-minute structure only when price reaches meaningful daily context.
3. Write results to terminal and Obsidian.

## Quick Start

```bash
cd sell-monitor
python -m sell_monitor.app.main
```

## Core Configuration

Configuration is loaded from `.env` in the project root by default.

### Provider

```dotenv
SELL_MONITOR_PROVIDER=akshare
```

Available values:

- `static`
- `akshare`
- `baostock`

### Obsidian Sell Monitor Output

```dotenv
SELL_MONITOR_OBSIDIAN_MONITOR_ENABLED=true
SELL_MONITOR_OBSIDIAN_MONITOR_DIR=E:\tools\OB\Obsidian\Trade\notes\monitor\sell
```

### Obsidian Entry Monitor Output

```dotenv
SELL_MONITOR_OBSIDIAN_ENTRY_ENABLED=true
SELL_MONITOR_OBSIDIAN_ENTRY_DIR=E:\tools\OB\Obsidian\Trade\notes\monitor\entry
```

### Obsidian Watchlists

The project now uses two separate watchlists in Obsidian:

```dotenv
SELL_MONITOR_SELL_WATCHLIST_PATH=E:\tools\OB\Obsidian\Trade\notes\monitor\config\sell-watchlist.md
SELL_MONITOR_ENTRY_WATCHLIST_PATH=E:\tools\OB\Obsidian\Trade\notes\monitor\config\entry-watchlist.md
```

- sell monitor reads `sell-watchlist.md`
- entry monitor reads `entry-watchlist.md`
- if one symbol should appear in both workflows, add it to both files

Format example:

```json
{
  "symbols": [
    { "symbol": "002241", "name": "歌尔股份" },
    { "symbol": "300015", "name": "爱尔眼科" },
    "300014"
  ]
}
```

## Helper Scripts

### Sell monitor

```powershell
.\scripts\run_akshare.ps1
.\scripts\run_akshare.ps1 -Loop -IntervalSeconds 3600
.\scripts\replay_advice.ps1 -Symbol 002241 -AsOfDate 2026-05-20
.\scripts\backtest_strategy.ps1 -Symbols "002241,002739" -StartDate 2025-11-20 -EndDate 2026-05-27
```

### Entry monitor

```powershell
.\scripts\scan_entry.ps1
.\scripts\scan_entry.ps1 -Symbol 002241
.\scripts\scan_entry.ps1 -Loop -IntervalSeconds 3600
.\scripts\replay_entry.ps1 -Symbol 002241 -AsOfDate 2026-05-20
.\scripts\backtest_entry.ps1 -Symbols "002241,300015" -StartDate 2025-11-20 -EndDate 2026-05-27
```

## Notes

- Real-time scans only run during normal A-share trading hours unless `--ignore-trading-hours` is used.
- If online data sources fail, the system may fall back to local cache depending on provider availability.
- Backtest and replay depth for 15-minute data still depends on the local cache plus upstream data-source history limits.
