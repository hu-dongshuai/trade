@echo off
setlocal
set "SELL_MONITOR_ENV_FILE=E:\tools\OB\Obsidian\Trade\notes\monitor\config\sell-monitor-config.md"
cd /d "C:\Users\admin\Documents\New project\sell-monitor"
powershell -ExecutionPolicy Bypass -File ".\scripts\backtest_entry.ps1" -Symbols "002241,300015" -StartDate 2025-11-20 -EndDate 2026-05-27
endlocal
