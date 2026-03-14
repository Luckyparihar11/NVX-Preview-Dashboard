# NVX Dashboard - Quick Install Script
# Right-click -> Run with PowerShell

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   NVX Dashboard - Quick Install" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# ── Python ─────────────────────────────────────────────────
Write-Host "Checking Python..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    $v = python --version 2>&1
    Write-Host "[OK] $v already installed" -ForegroundColor Green
} else {
    Write-Host "[..] Installing Python 3.12 via winget..." -ForegroundColor Yellow
    winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Write-Host "[OK] Python installed" -ForegroundColor Green
}

# ── pip upgrade ────────────────────────────────────────────
Write-Host ""
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet
Write-Host "[OK] pip upgraded" -ForegroundColor Green

# ── fastapi ────────────────────────────────────────────────
Write-Host ""
Write-Host "Installing fastapi..." -ForegroundColor Yellow
python -m pip install "fastapi>=0.111.0" --quiet
Write-Host "[OK] fastapi installed" -ForegroundColor Green

# ── uvicorn ────────────────────────────────────────────────
Write-Host ""
Write-Host "Installing uvicorn..." -ForegroundColor Yellow
python -m pip install "uvicorn[standard]>=0.29.0" --quiet
Write-Host "[OK] uvicorn installed" -ForegroundColor Green

# ── aiohttp ────────────────────────────────────────────────
Write-Host ""
Write-Host "Installing aiohttp..." -ForegroundColor Yellow
python -m pip install aiohttp --quiet
Write-Host "[OK] aiohttp installed" -ForegroundColor Green

# ── Summary ────────────────────────────────────────────────
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   All Done - Verification" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
python --version
python -m pip show fastapi | Select-String "Name|Version"
python -m pip show uvicorn | Select-String "Name|Version"
python -m pip show aiohttp | Select-String "Name|Version"
Write-Host ""
Write-Host "Run the dashboard with:" -ForegroundColor White
Write-Host "  python app.py" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to exit"
