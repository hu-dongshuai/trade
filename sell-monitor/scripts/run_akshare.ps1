param(
    [string]$Symbol = "",
    [switch]$Loop,
    [switch]$IgnoreTradingHours,
    [int]$IntervalSeconds = 3600,
    [string]$PythonExe = "C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

Push-Location $projectRoot
try {
    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env from .env.example. Please fill in SMTP values before production use."
    }

    do {
        $runAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Write-Host "[$runAt] Running sell monitor..."
        $argsList = @("-m", "sell_monitor.app.main")
        if ($Symbol) {
            $argsList += @("--symbol", $Symbol)
        }
        if ($IgnoreTradingHours) {
            $argsList += "--ignore-trading-hours"
        }
        & $PythonExe @argsList

        if ($Loop) {
            Write-Host "Next run after $IntervalSeconds seconds."
            Start-Sleep -Seconds $IntervalSeconds
        }
    } while ($Loop)
}
finally {
    Pop-Location
}
