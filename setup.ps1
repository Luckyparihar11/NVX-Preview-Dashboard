# NVX Preview Dashboard - Dependency Installer
# Run this script once before starting the dashboard
# Right-click this file -> Run with PowerShell
# OR in PowerShell: .\setup.ps1

$ErrorActionPreference = "Stop"

function Write-Header {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "   NVX Preview Dashboard - Dependency Installer" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Text)
    Write-Host "[....] $Text" -ForegroundColor Yellow -NoNewline
}

function Write-OK {
    param([string]$Text = "")
    Write-Host "`r[ OK ] $Text          " -ForegroundColor Green
}

function Write-Fail {
    param([string]$Text)
    Write-Host "`r[FAIL] $Text" -ForegroundColor Red
}

function Write-Skip {
    param([string]$Text)
    Write-Host "`r[SKIP] $Text - already installed" -ForegroundColor DarkGray
}

# ══════════════════════════════════════════════════════════
#  START
# ══════════════════════════════════════════════════════════
Write-Header

# ── Step 1: Check Windows version ─────────────────────────
Write-Step "Checking Windows version..."
$os = Get-WmiObject -Class Win32_OperatingSystem
$winVer = [System.Environment]::OSVersion.Version.Major
if ($winVer -ge 10) {
    Write-OK "Windows $($os.Caption)"
} else {
    Write-Fail "Windows 10 or later required. Found: $($os.Caption)"
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Step 2: Check / Install Python ────────────────────────
Write-Step "Checking Python..."
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    $pyVersion = python --version 2>&1
    Write-OK "$pyVersion"
} else {
    Write-Host "`r[....] Python not found. Installing via winget..." -ForegroundColor Yellow
    try {
        winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements --silent
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        $pyVersion = python --version 2>&1
        Write-OK "Python installed: $pyVersion"
    } catch {
        Write-Fail "Could not install Python automatically"
        Write-Host "  Please install manually: https://www.python.org/downloads/" -ForegroundColor Red
        Write-Host "  During install, tick 'Add Python to PATH'" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# ── Step 3: Upgrade pip ────────────────────────────────────
Write-Step "Upgrading pip..."
try {
    python -m pip install --upgrade pip --quiet
    $pipVersion = python -m pip --version
    Write-OK "$pipVersion"
} catch {
    Write-Fail "pip upgrade failed - continuing anyway"
}

# ── Step 4: Install FastAPI ────────────────────────────────
Write-Step "Installing fastapi..."
try {
    $installed = python -m pip show fastapi 2>&1
    if ($installed -match "Version") {
        $ver = ($installed | Select-String "Version").ToString().Trim()
        Write-Skip "fastapi ($ver)"
    } else {
        python -m pip install "fastapi>=0.111.0" --quiet
        $ver = (python -m pip show fastapi | Select-String "Version").ToString().Trim()
        Write-OK "fastapi installed ($ver)"
    }
} catch {
    Write-Fail "fastapi install failed: $_"
}

# ── Step 5: Install uvicorn ────────────────────────────────
Write-Step "Installing uvicorn..."
try {
    $installed = python -m pip show uvicorn 2>&1
    if ($installed -match "Version") {
        $ver = ($installed | Select-String "Version").ToString().Trim()
        Write-Skip "uvicorn ($ver)"
    } else {
        python -m pip install "uvicorn[standard]>=0.29.0" --quiet
        $ver = (python -m pip show uvicorn | Select-String "Version").ToString().Trim()
        Write-OK "uvicorn installed ($ver)"
    }
} catch {
    Write-Fail "uvicorn install failed: $_"
}

# ── Step 6: Install aiohttp ────────────────────────────────
Write-Step "Installing aiohttp..."
try {
    $installed = python -m pip show aiohttp 2>&1
    if ($installed -match "Version") {
        $ver = ($installed | Select-String "Version").ToString().Trim()
        Write-Skip "aiohttp ($ver)"
    } else {
        python -m pip install aiohttp --quiet
        $ver = (python -m pip show aiohttp | Select-String "Version").ToString().Trim()
        Write-OK "aiohttp installed ($ver)"
    }
} catch {
    Write-Fail "aiohttp install failed: $_"
}

# ── Step 6b: Install python-multipart ────────────────────
Write-Step "Installing python-multipart..."
try {
    $installed = python -m pip show python-multipart 2>&1
    if ($installed -match "Version") {
        $ver = ($installed | Select-String "Version").ToString().Trim()
        Write-Skip "python-multipart ($ver)"
    } else {
        python -m pip install python-multipart --quiet
        $ver = (python -m pip show python-multipart | Select-String "Version").ToString().Trim()
        Write-OK "python-multipart installed ($ver)"
    }
} catch {
    Write-Fail "python-multipart install failed: $_"
}

# ── Step 7: Install FFmpeg (optional) ─────────────────────
Write-Step "Checking FFmpeg..."
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
$bundled = Test-Path ".\ffmpeg\ffmpeg.exe"

if ($ffmpeg) {
    $ffVer = (ffmpeg -version 2>&1 | Select-Object -First 1).ToString().Trim()
    Write-OK "FFmpeg on PATH: $ffVer"
} elseif ($bundled) {
    Write-OK "FFmpeg found (bundled): .\ffmpeg\ffmpeg.exe"
} else {
    Write-Host "`r[....] FFmpeg not found. Installing via winget..." -ForegroundColor Yellow
    try {
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if ($winget) {
            winget install --id=Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements --silent
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            Write-OK "FFmpeg installed via winget"
        } else {
            Write-Host "`r[WARN] winget not available. Downloading FFmpeg manually..." -ForegroundColor Yellow
            $ffDir  = ".\ffmpeg"
            $zipPath = "$env:TEMP\ffmpeg-nvx.zip"
            $extractTo = "$env:TEMP\ffmpeg-nvx-extract"
            $url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

            New-Item -ItemType Directory -Path $ffDir -Force | Out-Null
            $wc = New-Object System.Net.WebClient
            Write-Host "     Downloading (~80MB)..." -ForegroundColor DarkGray
            $wc.DownloadFile($url, $zipPath)
            Expand-Archive -Path $zipPath -DestinationPath $extractTo -Force
            $ffexe = Get-ChildItem -Path $extractTo -Recurse -Filter "ffmpeg.exe" |
                     Where-Object { $_.DirectoryName -like "*\bin" } |
                     Select-Object -First 1
            if ($ffexe) {
                Copy-Item $ffexe.FullName -Destination "$ffDir\ffmpeg.exe" -Force
                Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
                Remove-Item $extractTo -Recurse -Force -ErrorAction SilentlyContinue
                Write-OK "FFmpeg installed to .\ffmpeg\ffmpeg.exe"
            } else {
                Write-Host "`r[WARN] FFmpeg download failed. Dashboard will still run (HTTP preview mode)" -ForegroundColor Yellow
            }
        }
    } catch {
        Write-Host "`r[WARN] FFmpeg install failed: $_ - Dashboard still works without it" -ForegroundColor Yellow
    }
}

# ── Step 8: Install PyInstaller (for building .exe) ───────
Write-Step "Installing pyinstaller (for building .exe)..."
try {
    $installed = python -m pip show pyinstaller 2>&1
    if ($installed -match "Version") {
        $ver = ($installed | Select-String "Version").ToString().Trim()
        Write-Skip "pyinstaller ($ver)"
    } else {
        python -m pip install pyinstaller --quiet
        $ver = (python -m pip show pyinstaller | Select-String "Version").ToString().Trim()
        Write-OK "pyinstaller installed ($ver)"
    }
} catch {
    Write-Fail "pyinstaller install failed (not critical - only needed to build .exe)"
}

# ── Step 9: Verify all packages ───────────────────────────
Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Verification Summary" -ForegroundColor White
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray

$packages = @("fastapi", "uvicorn", "aiohttp", "python-multipart", "pyinstaller")
foreach ($pkg in $packages) {
    $info = python -m pip show $pkg 2>&1
    if ($info -match "Version: (.+)") {
        $ver = $Matches[1].Trim()
        Write-Host "  [OK] $pkg $ver" -ForegroundColor Green
    } else {
        Write-Host "  [!!] $pkg NOT INSTALLED" -ForegroundColor Red
    }
}

# Python version
$pyVer = python --version 2>&1
Write-Host "  [OK] $pyVer" -ForegroundColor Green

# FFmpeg
$ff = Get-Command ffmpeg -ErrorAction SilentlyContinue
$ffBundled = Test-Path ".\ffmpeg\ffmpeg.exe"
if ($ff -or $ffBundled) {
    Write-Host "  [OK] FFmpeg available" -ForegroundColor Green
} else {
    Write-Host "  [--] FFmpeg not found (optional - HTTP preview mode works without it)" -ForegroundColor DarkGray
}

# ── Step 10: Check devices.json ───────────────────────────
Write-Host ""
if (Test-Path ".\devices.json") {
    Write-Host "  [OK] devices.json found" -ForegroundColor Green
} else {
    Write-Host "  [!!] devices.json NOT found - create it with your NVX device IPs" -ForegroundColor Yellow
}

if (Test-Path ".\settings.json") {
    Write-Host "  [OK] settings.json found" -ForegroundColor Green
} else {
    Write-Host "  [!!] settings.json NOT found - will be created on first run" -ForegroundColor Yellow
}

if (Test-Path ".\static\index.html") {
    Write-Host "  [OK] static\index.html found" -ForegroundColor Green
} else {
    Write-Host "  [!!] static\index.html NOT found - dashboard UI missing" -ForegroundColor Red
}

if (Test-Path ".\app.py") {
    Write-Host "  [OK] app.py found" -ForegroundColor Green
} else {
    Write-Host "  [!!] app.py NOT found - main server file missing" -ForegroundColor Red
}

# ── Port 8000 conflict check ───────────────────────────────
Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Port Check" -ForegroundColor White
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
$port = 8000
if (Test-Path ".\settings.json") {
    try {
        $s = Get-Content ".\settings.json" | ConvertFrom-Json
        if ($s.port) { $port = $s.port }
    } catch {}
}
$portInUse = netstat -ano | Select-String ":$port " | Select-String "LISTENING"
if ($portInUse) {
    Write-Host "  [!!] Port $port is already in use - change 'port' in settings.json" -ForegroundColor Yellow
    Write-Host "       Or stop the process using it before running app.py" -ForegroundColor Yellow
} else {
    Write-Host "  [OK] Port $port is free and ready to use" -ForegroundColor Green
}

# ── Done ───────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   Setup Complete" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  To start the dashboard:" -ForegroundColor White
Write-Host "    python app.py" -ForegroundColor Green
Write-Host ""
Write-Host "  Or double-click START_DASHBOARD.bat" -ForegroundColor White
Write-Host ""
Write-Host "  Browser will open automatically at http://localhost:8000" -ForegroundColor DarkGray
Write-Host ""

Read-Host "Press Enter to exit"
