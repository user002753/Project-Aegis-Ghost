@echo off
setlocal

cd /d "%~dp0frontend"

echo [Aegis Ghost] Starting frontend on http://127.0.0.1:3000
echo.

set PORT=3000
npm start

echo.
echo Frontend process exited. Press any key to close.
pause >nul

