@echo off
setlocal
set "SELL_MONITOR_ENV_FILE=E:\tools\OB\Obsidian\Trade\notes\monitor\config\sell-monitor-config.md"
cd /d "C:\Users\admin\Documents\New project\sell-monitor"
powershell -ExecutionPolicy Bypass -File ".\scripts\run_akshare.ps1"
endlocal
