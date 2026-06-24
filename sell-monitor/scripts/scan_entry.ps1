param(
    [string]$Symbol = "",
    [switch]$Loop,
    [switch]$IgnoreTradingHours,
    [int]$IntervalSeconds = 3600,
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
. (Join-Path $scriptDir "_python.ps1")
. (Join-Path $scriptDir "_config.ps1")
$resolvedPythonExe = Resolve-SellMonitorPython -ProjectRoot $projectRoot -PreferredPythonExe $PythonExe

Push-Location $projectRoot
try {
    $resolvedConfig = Set-SellMonitorConfigEnv -ProjectRoot $projectRoot
    do {
        $runAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Write-Host "[$runAt] Running entry monitor with Python: $resolvedPythonExe"
        Write-Host "Using config: $resolvedConfig"
        $argsList = @("-m", "sell_monitor.app.entry_scan")
        if ($Symbol) {
            $argsList += @("--symbol", $Symbol)
        }
        if ($IgnoreTradingHours) {
            $argsList += "--ignore-trading-hours"
        }
        & $resolvedPythonExe @argsList

        if ($Loop) {
            Write-Host "Next run after $IntervalSeconds seconds."
            Start-Sleep -Seconds $IntervalSeconds
        }
    } while ($Loop)
}
finally {
    Pop-Location
}
