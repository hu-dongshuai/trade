@echo off
setlocal
set "SELL_MONITOR_ENV_FILE=E:\tools\OB\Obsidian\Trade\notes\monitor\config\sell-monitor-config.md"
cd /d "C:\Users\admin\Documents\New project\sell-monitor"
powershell -ExecutionPolicy Bypass -File ".\scripts\replay_entry.ps1" -Symbol 002241 -AsOfDate 2026-05-20
endlocal
