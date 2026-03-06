@echo off
REM ============================================
REM Project Aegis Ghost - Portable Launcher
REM ============================================

echo Starting Project Aegis Ghost...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9 or higher from https://python.org
    pause
    exit /b 1
)

REM Check if Node.js is available (for frontend)
node --version >nul 2>&1
set NODE_AVAILABLE=%errorlevel%

REM Install Python dependencies if needed
echo Checking Python dependencies...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Installing Python dependencies...
    pip install -r requirements.txt
)

REM Check if frontend is built
if not exist "frontend\build" (
    echo.
    echo Frontend not built. Building now...
    cd frontend
    call npm install
    call npm run build
    cd ..
)

REM Start the backend server
echo.
echo Starting server on http://localhost:8000
echo Press Ctrl+C to stop the server
echo.

REM Start server and keep it running
python server.py

pause
