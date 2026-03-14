# install_ffmpeg.ps1
# Right-click this file → "Run with PowerShell"
# Installs FFmpeg for the NVX Preview Dashboard

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  FFmpeg Installer for NVX Dashboard" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Already on PATH?
$existing = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[OK] FFmpeg already installed: $($existing.Source)" -ForegroundColor Green
    ffmpeg -version 2>&1 | Select-Object -First 1
    Read-Host "`nPress Enter to exit"
    exit 0
}

# Bundled copy?
$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$bundlePath = Join-Path $scriptDir "ffmpeg\ffmpeg.exe"
if (Test-Path $bundlePath) {
    Write-Host "[OK] Bundled FFmpeg found: $bundlePath" -ForegroundColor Green
    Read-Host "`nPress Enter to exit"
    exit 0
}

Write-Host "FFmpeg not found. Trying to install..." -ForegroundColor Yellow
Write-Host ""

# Option A: winget
$winget = Get-Command winget -ErrorAction SilentlyContinue
if ($winget) {
    Write-Host "[1] Trying winget (Gyan.FFmpeg)..." -ForegroundColor Cyan
    try {
        winget install --id=Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
        Write-Host ""
        Write-Host "[OK] FFmpeg installed via winget!" -ForegroundColor Green
        Write-Host "     Close this window, then run START_DASHBOARD.bat" -ForegroundColor Green
        Read-Host "`nPress Enter to exit"
        exit 0
    } catch {
        Write-Host "     winget failed — trying manual download..." -ForegroundColor Yellow
    }
}

# Option B: Direct download to .\ffmpeg\ffmpeg.exe
Write-Host "[2] Downloading FFmpeg from gyan.dev (~80 MB)..." -ForegroundColor Cyan
$ffmpegDir = Join-Path $scriptDir "ffmpeg"
$zipPath   = "$env:TEMP\ffmpeg-nvx.zip"
$extractTo = "$env:TEMP\ffmpeg-nvx-extract"
$url       = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Write-Host "     Downloading..." -NoNewline
    $wc = New-Object System.Net.WebClient
    $wc.DownloadFile($url, $zipPath)
    Write-Host " done" -ForegroundColor Green

    Write-Host "     Extracting..." -NoNewline
    if (Test-Path $extractTo) { Remove-Item $extractTo -Recurse -Force }
    Expand-Archive -Path $zipPath -DestinationPath $extractTo -Force
    Write-Host " done" -ForegroundColor Green

    $ffexe = Get-ChildItem -Path $extractTo -Recurse -Filter "ffmpeg.exe" |
             Where-Object { $_.DirectoryName -like "*\bin" } |
             Select-Object -First 1

    if (-not $ffexe) { throw "ffmpeg.exe not found in zip" }

    if (-not (Test-Path $ffmpegDir)) { New-Item -ItemType Directory -Path $ffmpegDir | Out-Null }
    Copy-Item $ffexe.FullName -Destination (Join-Path $ffmpegDir "ffmpeg.exe") -Force

    # Cleanup temp files
    Remove-Item $zipPath   -Force -ErrorAction SilentlyContinue
    Remove-Item $extractTo -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "[OK] FFmpeg installed to: $ffmpegDir\ffmpeg.exe" -ForegroundColor Green
    Write-Host "     Run START_DASHBOARD.bat to start the dashboard." -ForegroundColor Green

} catch {
    Write-Host ""
    Write-Host "[ERROR] Automatic install failed: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Manual steps:" -ForegroundColor Yellow
    Write-Host "  1. Go to: https://www.gyan.dev/ffmpeg/builds/"
    Write-Host "  2. Download: ffmpeg-release-essentials.zip"
    Write-Host "  3. Open zip → go into bin\ folder"
    Write-Host "  4. Copy ffmpeg.exe to: $ffmpegDir\ffmpeg.exe"
}

Write-Host ""
Read-Host "Press Enter to exit"
