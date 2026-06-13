$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "py"
}

& $python -m pip install -e "${root}[build]"
& $python -m PyInstaller --clean --noconfirm (Join-Path $root "67-counter.spec")

$releaseDir = Join-Path $root "release"
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
Copy-Item -Force (Join-Path $root "dist\67-counter.exe") (Join-Path $releaseDir "67-counter-v1.0.0-windows-x64.exe")
Write-Host "Built release\67-counter-v1.0.0-windows-x64.exe"
