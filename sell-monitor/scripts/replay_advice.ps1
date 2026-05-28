param(
    [Parameter(Mandatory = $true)]
    [string]$Symbol,
    [Parameter(Mandatory = $true)]
    [string]$AsOfDate,
    [string]$PythonExe = "C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

Push-Location $projectRoot
try {
    & $PythonExe -m sell_monitor.app.replay --symbol $Symbol --as-of-date $AsOfDate
}
finally {
    Pop-Location
}
