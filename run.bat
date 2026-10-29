@echo off
title LedgerGPT Enterprise Launcher
echo =======================================================
echo   Launching LedgerGPT Enterprise Cockpit...
echo =======================================================
cd /d "%~dp0"

echo [1/2] Starting local intelligence server on port 5000...
start "" python run_web.py

echo [2/2] Opening web dashboard in default browser...
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:5000"

echo.
echo LedgerGPT is running!
echo Access live at: http://127.0.0.1:5000
echo (Close this terminal window or press Ctrl+C when done)
echo.
pause
