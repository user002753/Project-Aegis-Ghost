@echo off
setlocal

cd /d "%~dp0"

echo [Aegis Ghost] Starting backend on http://127.0.0.1:8000
echo.

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" server.py
) else if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" server.py
) else (
  python server.py
)

echo.
echo Backend process exited. Press any key to close.
pause >nul

