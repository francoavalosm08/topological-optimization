$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

Write-Host "Generating packaged sample STLs..."
python scripts/z88_generate_samples.py --output samples | Out-Host

Write-Host "Running packaging preflight..."
python scripts/z88_packaging_preflight.py `
  --require-packager `
  --output z88_assets\outputs\packaging_preflight.json | Out-Host

Write-Host "Building PyInstaller executable..."
pyinstaller --clean --noconfirm packaging\Z88TopologyOptimizer.spec

$Exe = Join-Path $Root "dist\Z88TopologyOptimizer.exe"
if (-not (Test-Path $Exe)) {
  throw "Expected packaged executable was not created: $Exe"
}

Write-Host "Running packaged smoke test..."
& $Exe --smoke-test --no-browser --allow-missing-z88 | Out-Host
if ($LASTEXITCODE -ne 0) {
  throw "Packaged smoke test failed with exit code $LASTEXITCODE"
}

Write-Host "Package build complete: $Exe"
