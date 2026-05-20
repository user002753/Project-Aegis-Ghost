@echo off
setlocal
cd /d "%~dp0"

echo [Aegis Ghost] Starting backend on http://127.0.0.1:8000
start "Aegis Backend :8000" cmd /k ""%~dp0RUN_BACKEND_8000.bat""

echo [Aegis Ghost] Starting frontend on http://127.0.0.1:8000
start "Aegis Frontend :8000" cmd /k ""%~dp0RUN_FRONTEND_3000.bat""

echo.
echo Started both services:
echo   Backend : http://127.0.0.1:8000
echo   Frontend: http://127.0.0.1:3000
echo.
