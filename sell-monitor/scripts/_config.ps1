function Set-SellMonitorConfigEnv {
    param(
        [string]$ProjectRoot
    )

    $obsidianConfig = "E:\tools\OB\Obsidian\Trade\notes\monitor\config\sell-monitor-config.md"
    $localConfig = Join-Path $ProjectRoot ".env"

    if (Test-Path -LiteralPath $obsidianConfig) {
        $env:SELL_MONITOR_ENV_FILE = $obsidianConfig
        return $obsidianConfig
    }

    $env:SELL_MONITOR_ENV_FILE = $localConfig
    return $localConfig
}
