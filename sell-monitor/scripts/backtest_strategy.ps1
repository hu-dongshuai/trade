param(
    [string[]]$Symbols = @(),
    [Parameter(Mandatory = $true)]
    [string]$StartDate,
    [Parameter(Mandatory = $true)]
    [string]$EndDate,
    [string]$Output = "",
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
    $argsList = @("-m", "sell_monitor.app.backtest", "--start-date", $StartDate, "--end-date", $EndDate)
    if ($Symbols.Count -gt 0) {
        $normalizedSymbols = foreach ($item in $Symbols) {
            foreach ($part in ($item -split ",")) {
                $text = $part.Trim()
                if ($text -match '^\d{1,5}$') {
                    $text.PadLeft(6, '0')
                }
                elseif ($text) {
                    $text
                }
            }
        }
        $symbolText = ($normalizedSymbols -join ",")
        $argsList += @("--symbols", $symbolText)
    }
    if ($Output) {
        $argsList += @("--output", $Output)
    }
    Write-Host "Using Python: $resolvedPythonExe"
    Write-Host "Using config: $resolvedConfig"
    & $resolvedPythonExe @argsList
}
finally {
    Pop-Location
}
