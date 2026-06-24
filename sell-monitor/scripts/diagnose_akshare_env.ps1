param(
    [string]$Symbol = "002739",
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
. (Join-Path $scriptDir "_python.ps1")
$resolvedPythonExe = Resolve-SellMonitorPython -ProjectRoot $projectRoot -PreferredPythonExe $PythonExe

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "=== $Title ==="
}

function Get-EnvEntries {
    $lines = cmd /c set
    foreach ($line in $lines) {
        if ($line -match "^(.*?)=(.*)$") {
            [pscustomobject]@{
                Name  = $matches[1]
                Lower = $matches[1].ToLowerInvariant()
                Value = $matches[2]
            }
        }
    }
}

Push-Location $projectRoot
try {
    Write-Section "Duplicate Environment Keys"
    $envEntries = @(Get-EnvEntries)
    $duplicates = $envEntries | Group-Object Lower | Where-Object { $_.Count -gt 1 }
    if (-not $duplicates) {
        Write-Host "No case-insensitive duplicate environment keys found."
    }
    else {
        foreach ($group in $duplicates) {
            Write-Host ("Key group: " + $group.Name)
            $group.Group | ForEach-Object { Write-Host ("  {0}={1}" -f $_.Name, $_.Value) }
        }
    }

    Write-Section "Proxy"
    $proxyLines = cmd /c set | findstr /i proxy
    if ($proxyLines) {
        $proxyLines | ForEach-Object { Write-Host $_ }
    }
    else {
        Write-Host "No proxy-related process environment variables."
    }
    netsh winhttp show proxy

    Write-Section "TCP Connectivity"
    foreach ($hostName in @("push2his.eastmoney.com", "quotes.sina.cn", "finance.sina.com.cn")) {
        Test-NetConnection $hostName -Port 443 |
            Select-Object ComputerName, RemoteAddress, RemotePort, TcpTestSucceeded
    }

    Write-Section "Direct HTTP Requests"
    $httpCode = @'
import requests

tests = [
    (
        "eastmoney_m15",
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "klt": "15",
            "fqt": "1",
            "secid": "0.__SYMBOL__",
            "beg": "0",
            "end": "20500000",
        },
    ),
    (
        "sina_m15",
        "https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData",
        {"symbol": "sz__SYMBOL__", "scale": "15", "ma": "no", "datalen": "20"},
    ),
]

for name, url, params in tests:
    print("===", name, "===")
    try:
        response = requests.get(url, params=params, timeout=20)
        print("status", response.status_code)
        print("content-type", response.headers.get("content-type"))
        print(response.text[:200].replace("\\n", " "))
    except Exception as exc:
        print(type(exc).__name__, exc)
'@
    $httpCode = $httpCode.Replace("__SYMBOL__", $Symbol)
    $httpTemp = New-TemporaryFile
    try {
        Set-Content -LiteralPath $httpTemp.FullName -Value $httpCode -Encoding UTF8
        Write-Host "Using Python: $resolvedPythonExe"
        & $resolvedPythonExe $httpTemp.FullName
    }
    finally {
        Remove-Item -LiteralPath $httpTemp.FullName -ErrorAction SilentlyContinue
    }

    Write-Section "AkShare Calls"
    $akCode = @'
import akshare as ak
import traceback

tests = [
    ("stock_zh_a_spot_em", lambda: ak.stock_zh_a_spot_em().head(1)),
    ("stock_zh_a_hist_min_em", lambda: ak.stock_zh_a_hist_min_em(symbol="__SYMBOL__", period="15", adjust="qfq").tail(2)),
    ("stock_zh_a_minute_qfq", lambda: ak.stock_zh_a_minute(symbol="sz__SYMBOL__", period="15", adjust="qfq").tail(2)),
]

for name, func in tests:
    print("===", name, "===")
    try:
        print(func().to_string())
    except Exception as exc:
        print(type(exc).__name__, exc)
        traceback.print_exc(limit=1)
'@
    $akCode = $akCode.Replace("__SYMBOL__", $Symbol)
    $akTemp = New-TemporaryFile
    try {
        Set-Content -LiteralPath $akTemp.FullName -Value $akCode -Encoding UTF8
        & $resolvedPythonExe $akTemp.FullName
    }
    finally {
        Remove-Item -LiteralPath $akTemp.FullName -ErrorAction SilentlyContinue
    }
}
finally {
    Pop-Location
}
