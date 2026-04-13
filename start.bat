@echo off
title EduAnalytics AI - Starting...
echo ============================================
echo    EduAnalytics AI - Student Analytics App
echo ============================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python from https://python.org
    pause
    exit /b
)

:: Install Flask and requests if not already installed
echo [1/2] Installing dependencies...
pip install flask requests >nul 2>&1
echo       Done.

:: Set Groq API key from .env file
if exist .env (
    for /f "tokens=1,2 delims==" %%a in (.env) do set %%a=%%b
)

echo [2/2] Starting EduAnalytics server...
echo.
echo ============================================
echo   App running at: http://127.0.0.1:5000
echo   Login: admin / 1234
echo   AI Analysis: Groq Llama 3.3 70B
echo ============================================
echo   Press Ctrl+C to stop the server
echo ============================================
echo.

python app.py

pause
