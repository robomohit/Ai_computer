@echo off
setlocal

echo.
echo  ============================================
echo    AI Computer - Setup
echo  ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo [1/3] Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed. Check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo [2/3] Installing Playwright browser (Chromium)...
playwright install chromium
if errorlevel 1 (
    echo [WARN] Playwright install failed - browser/computer-use mode won't work.
    echo        You can retry later with: playwright install chromium
)

echo.
echo [3/3] Creating .env file...
if not exist .env (
    copy .env.example .env >nul
    echo   Created .env from .env.example
    echo   ^>^> Open .env and add at least one API key before launching.
) else (
    echo   .env already exists, skipping.
)

echo.
echo  ============================================
echo    Setup complete!
echo.
echo    Next steps:
echo      1. Edit .env and add your API key
echo         (free option: get OPENROUTER_API_KEY at openrouter.ai)
echo      2. Double-click start.bat to launch
echo  ============================================
echo.
pause
