@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" (
    for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "py -0p 2>$null | Where-Object { $_ -match '3\.12' -and $_ -notmatch 'arm64' } | ForEach-Object { ($_.Trim() -split '\s+', 2)[-1].Trim() } | Select-Object -First 1" 2^>nul`) do set "AMD64_PY=%%P"
    if defined AMD64_PY if exist "!AMD64_PY!" (
        for %%F in ("!AMD64_PY!") do set "PATH=%%~dpF;%PATH%"
        python kert_gui.py
    ) else (
        py -3.12 kert_gui.py
    )
) else (
    py -3.12 kert_gui.py
)
pause
