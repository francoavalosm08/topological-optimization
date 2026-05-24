param(
    [string]$Exe = "dist\Z88TopologyOptimizer.exe",
    [int]$Port = 8020,
    [switch]$AllowMissingZ88,
    [string]$Output = "z88_assets\outputs\clean_vm_validation.json"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

function Stop-PackagedServerForPort {
    param(
        [string]$ExeFullPath,
        [int]$Port
    )
    $escapedPort = "--port $Port"
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.ExecutablePath -eq $ExeFullPath -and
            $_.CommandLine -like "*$escapedPort*"
        } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

$ExePath = Resolve-Path $Exe -ErrorAction SilentlyContinue
if (-not $ExePath) {
    throw "Packaged executable not found: $Exe"
}

$result = [ordered]@{
    schema_version = 1
    status = "failed"
    root = $Root.Path
    exe = $ExePath.Path
    allow_missing_z88 = [bool]$AllowMissingZ88
    smoke_test = $null
    server_smoke = $null
}

$smokeArgs = @("--smoke-test", "--no-browser")
if ($AllowMissingZ88) {
    $smokeArgs += "--allow-missing-z88"
}

$smoke = & $ExePath.Path @smokeArgs 2>&1
$smokeExit = $LASTEXITCODE
$result.smoke_test = [ordered]@{
    exit_code = $smokeExit
    output_tail = (($smoke | Out-String).Trim() -replace "`r", "")
}
if ($smokeExit -ne 0) {
    $out = Split-Path -Parent (Join-Path $Root $Output)
    New-Item -ItemType Directory -Path $out -Force | Out-Null
    $result | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $Root $Output) -Encoding UTF8
    exit 2
}

$proc = $null
$serverFailure = $null
try {
    $existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($existing) {
        throw "Port $Port is already in use"
    }

    $proc = Start-Process -FilePath $ExePath.Path `
        -ArgumentList @("--host", "127.0.0.1", "--port", "$Port", "--no-browser", "--log-level", "warning") `
        -WindowStyle Hidden `
        -PassThru

    $url = "http://127.0.0.1:$Port/"
    $response = $null
    for ($i = 0; $i -lt 20; $i++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2
            break
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $response) {
        throw "Packaged server did not respond on $url"
    }
    $content = [string]$response.Content
    $result.server_smoke = [ordered]@{
        url = $url
        status_code = [int]$response.StatusCode
        has_z88 = $content.Contains("Z88")
        has_generate_samples = $content.Contains("Generate Samples")
        has_native_project = $content.Contains("Generate Native OC Project")
    }
    if (-not $result.server_smoke.has_z88 -or -not $result.server_smoke.has_generate_samples) {
        throw "Packaged server responded but did not include expected Z88 UI controls"
    }
    $result.status = "ok"
} catch {
    $serverFailure = $_.Exception.Message
    $result.server_smoke = [ordered]@{
        error = $serverFailure
    }
} finally {
    if ($proc -and -not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force
    }
    Stop-PackagedServerForPort -ExeFullPath $ExePath.Path -Port $Port
}

$outputPath = Join-Path $Root $Output
New-Item -ItemType Directory -Path (Split-Path -Parent $outputPath) -Force | Out-Null
$result | ConvertTo-Json -Depth 8 | Set-Content -Path $outputPath -Encoding UTF8
$result | ConvertTo-Json -Depth 8
if ($serverFailure) {
    exit 2
}
