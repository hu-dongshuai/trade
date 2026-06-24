param(
    [Parameter(Mandatory = $true)]
    [string]$Symbol,
    [Parameter(Mandatory = $true)]
    [string]$StartDate,
    [Parameter(Mandatory = $true)]
    [string]$EndDate,
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
. (Join-Path $scriptDir "_python.ps1")
$resolvedPythonExe = Resolve-SellMonitorPython -ProjectRoot $projectRoot -PreferredPythonExe $PythonExe

Push-Location $projectRoot
try {
    Write-Host "Using Python: $resolvedPythonExe"
    & $resolvedPythonExe -m sell_monitor.app.diagnose_baostock --symbol $Symbol --start-date $StartDate --end-date $EndDate
}
finally {
    Pop-Location
}
