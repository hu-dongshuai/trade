param(
    [string]$PythonExe = "",
    [string]$Subject = "[SellMonitor] 测试邮件"
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
    Write-Host "Using config: $resolvedConfig"
    & $resolvedPythonExe -m sell_monitor.app.send_test_email --subject $Subject
}
finally {
    Pop-Location
}
