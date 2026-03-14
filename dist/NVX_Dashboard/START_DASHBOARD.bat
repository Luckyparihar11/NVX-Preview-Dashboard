@echo off
chcp 65001 >nul
title NVX Preview Dashboard
cd /d "%~dp0"

echo.
echo ============================================================
echo   NVX RTSP Preview Dashboard  v2.0
echo ============================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found on PATH.
    echo         Download: https://www.python.org/downloads/
    echo         During install, tick "Add Python to PATH"
    echo.
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [OK] %%v

:: Check / install pip packages
echo [..] Checking packages...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo [..] Installing fastapi + uvicorn...
    pip install fastapi "uvicorn[standard]" --quiet
    if errorlevel 1 (
        echo [ERROR] pip install failed. Check internet connection.
        pause & exit /b 1
    )
)
echo [OK] fastapi + uvicorn ready

:: Check devices.json
if not exist devices.json (
    echo [WARN] devices.json not found - app will create a template on first run
) else (
    echo [OK] devices.json found
)

:: Check FFmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    if exist ffmpeg\ffmpeg.exe (
        echo [OK] FFmpeg found ^(bundled^)
    ) else (
        echo [WARN] FFmpeg not found - devices will show OFFLINE
        echo        Run install_ffmpeg.ps1 to install it
    )
) else (
    echo [OK] FFmpeg found on PATH
)

:: Check static folder
if not exist static\index.html (
    echo [ERROR] static\index.html not found.
    echo         Make sure the static\ folder is in the same directory as app.py
    pause & exit /b 1
)
echo [OK] static\index.html found

echo.
echo [..] Starting server...
echo      Open browser: http://localhost:8000
echo      Press Ctrl+C to stop
echo.
echo ============================================================
echo.

python app.py

echo.
echo ============================================================
echo   Server stopped.
echo ============================================================
pause
