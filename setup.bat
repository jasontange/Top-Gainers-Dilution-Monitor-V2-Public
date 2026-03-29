@echo off
echo ============================================
echo  Ask Edgar Dilution Monitor - Setup
echo ============================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in your PATH.
    echo.
    echo Download Python from: https://www.python.org/downloads/
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo Found Python:
python --version
echo.

:: Install dependencies
echo Installing required packages...
pip install -r requirements.txt
echo.

:: Create .env if it doesn't exist
if not exist .env (
    copy .env.example .env
    echo.
    echo Created .env file from template.
    echo.
    echo ============================================
    echo  NEXT STEP: Add your API key
    echo ============================================
    echo.
    echo 1. Open the .env file in this folder
    echo 2. Replace "your_api_key_here" with your Ask Edgar API key
    echo 3. Save the file
    echo.
    echo Don't have keys? Request free trials at:
    echo   Ask Edgar: https://www.askedgar.io/api-trial
    echo   Massive:   https://massive.com
    echo.
) else (
    echo .env file already exists - skipping.
    echo.
)

echo Setup complete! Run the app with: python das_monitor.py
echo Or double-click run.bat
echo.
pause
