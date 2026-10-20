<#
.SYNOPSIS
  Builds CorporateFilingsDownloader.exe and packages a distributable zip.

.DESCRIPTION
  1. Uses (or creates) .venv and installs requirements-build.txt
  2. Runs PyInstaller against CorporateFilingsDownloader.spec
  3. Assembles release\CorporateFilingsDownloader-v<version>\ with the exe,
     HOW_TO_INSTALL_ON_OTHER_PCS.txt and LICENSE
  4. Zips it and writes SHA256 checksums for the exe and the zip

  Run from the repo root:
    powershell -ExecutionPolicy Bypass -File build_release.ps1
    powershell -ExecutionPolicy Bypass -File build_release.ps1 -Version 1.1.0
#>
param([string]$Version = "1.0.1")

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Creating .venv ..."
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create a virtual environment - is Python 3.10+ installed and on PATH?" }
}

Write-Host "Installing build requirements ..."
& $py -m pip install --quiet -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

# A running copy of the exe would lock the output file.
Get-Process -Name "CorporateFilingsDownloader" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500

Write-Host "Running PyInstaller ..."
& $py -m PyInstaller --noconfirm --clean --log-level WARN CorporateFilingsDownloader.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$exe = Join-Path $root "dist\CorporateFilingsDownloader.exe"
if (-not (Test-Path $exe)) { throw "Expected $exe was not produced" }

$name  = "CorporateFilingsDownloader-v$Version"
$stage = Join-Path $root "release\$name"
$zip   = Join-Path $root "release\$name-windows-x64.zip"

if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
if (Test-Path $zip)   { Remove-Item $zip -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

Copy-Item $exe $stage
Copy-Item (Join-Path $root "HOW_TO_INSTALL_ON_OTHER_PCS.txt") $stage
if (Test-Path (Join-Path $root "LICENSE")) { Copy-Item (Join-Path $root "LICENSE") $stage }

Compress-Archive -Path $stage -DestinationPath $zip -CompressionLevel Optimal

$sums = @(
    "$((Get-FileHash $exe -Algorithm SHA256).Hash.ToLower())  CorporateFilingsDownloader.exe",
    "$((Get-FileHash $zip -Algorithm SHA256).Hash.ToLower())  $name-windows-x64.zip"
)
$sums | Set-Content -Encoding ascii (Join-Path $root "release\SHA256SUMS.txt")

Write-Host ""
Write-Host "Done."
Write-Host "  exe : $exe"
Write-Host "  zip : $zip"
$sums | ForEach-Object { Write-Host "  $_" }
