param(
    [Parameter(Mandatory = $true)]
    [string]$Symbol,
    [Parameter(Mandatory = $true)]
    [string]$AsOfDate,
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
    Write-Host "Using Python: $resolvedPythonExe"
    Write-Host "Using config: $resolvedConfig"
    & $resolvedPythonExe -m sell_monitor.app.replay_entry --symbol $Symbol --as-of-date $AsOfDate
}
finally {
    Pop-Location
}
