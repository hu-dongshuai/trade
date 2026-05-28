param(
    [string[]]$Symbols = @(),
    [Parameter(Mandatory = $true)]
    [string]$StartDate,
    [Parameter(Mandatory = $true)]
    [string]$EndDate,
    [string]$Output = "",
    [string]$PythonExe = "C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

Push-Location $projectRoot
try {
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
    & $PythonExe @argsList
}
finally {
    Pop-Location
}
