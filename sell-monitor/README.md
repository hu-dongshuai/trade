# Sell Monitor

A local-first, rule-based sell-monitor project for Chinese stock trading workflows.

The project follows a two-layer process:

1. Use daily bars to build and rank major key price zones.
2. Only when price approaches an A/B daily zone, run 15-minute sell triggers.

The package ships with:

- a pluggable market data provider interface
- a static JSON provider for local development
- an AkShare live provider for A-share market data
- a rule engine for zones, signals, scoring, and final decisions
- sample data and unit tests
- console output, Obsidian Markdown logs, and SMTP email alert delivery

## Quick Start

```bash
cd sell-monitor
python -m sell_monitor.app.main
```

Or after installation:

```bash
sell-monitor
```

## AkShare and email

The default provider is `static`, which reads from `examples/market_data.json`.

To switch to AkShare, either export environment variables or copy `.env.example` to `.env`.

Minimal `.env`:

```dotenv
SELL_MONITOR_PROVIDER=akshare
```

To enable SMTP email alerts:

```dotenv
SELL_MONITOR_SMTP_HOST=smtp.example.com
SELL_MONITOR_SMTP_PORT=587
SELL_MONITOR_SMTP_USERNAME=you@example.com
SELL_MONITOR_SMTP_PASSWORD=your-app-password
SELL_MONITOR_EMAIL_FROM=you@example.com
SELL_MONITOR_EMAIL_TO=you@example.com
```

Obsidian monitor logs are enabled by default and are written one file per symbol:

```dotenv
SELL_MONITOR_OBSIDIAN_MONITOR_ENABLED=true
SELL_MONITOR_OBSIDIAN_MONITOR_DIR=E:\tools\OB\Obsidian\Trade\notes\monitor
```

Each run prepends the newest result to `{symbol}.md`, so the latest monitor result is always at the top.

When `SELL_MONITOR_PROVIDER=akshare`, the tool fetches:

- latest A-share quote from `stock_zh_a_spot_em()`
- daily bars from `stock_zh_a_hist()`
- 15-minute bars from `stock_zh_a_hist_min_em()`

## Backup data path

The AkShare path now uses a three-level fallback chain:

1. Eastmoney-backed AkShare endpoints
2. Sina-backed AkShare endpoints
3. Local cache in `runtime_cache/`

If the live endpoints fail but cached data exists, the tool falls back to the last successful local snapshot and prints a notice in the terminal.

## Helper scripts

Run the main monitor:

```powershell
.\scripts\run_akshare.ps1
```

Run continuously once per hour:

```powershell
.\scripts\run_akshare.ps1 -Loop -IntervalSeconds 3600
```

Run a live smoke test for Goertek (`002241`):

```powershell
C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe .\scripts\smoke_goertek_002241.py
```

Replay historical advice for one stock and one date:

```powershell
.\scripts\replay_advice.ps1 -Symbol 002241 -AsOfDate 2026-05-20
```

Batch backtest the sell strategy and write a Markdown report:

```powershell
.\scripts\backtest_strategy.ps1 -Symbols 002241,002739 -StartDate 2025-11-20 -EndDate 2026-05-27
```

When Obsidian monitor output is enabled, backtest reports are written under
`E:\tools\OB\Obsidian\Trade\notes\monitor\backtest`.
