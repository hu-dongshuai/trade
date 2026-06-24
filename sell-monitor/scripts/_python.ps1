function Resolve-SellMonitorPython {
    param(
        [string]$ProjectRoot,
        [string]$PreferredPythonExe = ""
    )

    $candidates = @()

    if ($PreferredPythonExe) {
        $candidates += $PreferredPythonExe
    }

    if ($ProjectRoot) {
        $venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
        $candidates += $venvPython
    }

    $candidates += "C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

    foreach ($candidate in $candidates) {
        if (-not $candidate) {
            continue
        }
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return $pythonCmd.Source
    }

    throw "No usable Python interpreter found. Pass -PythonExe explicitly or create .venv\\Scripts\\python.exe."
}
