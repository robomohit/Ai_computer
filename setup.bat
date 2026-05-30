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
    echo         Be sure to tick "Add python.exe to PATH" during install.
    pause
    exit /b 1
)

echo [1/3] Installing Python dependencies (desktop app + UI + UIA control)...
pip install -r requirements-desktop.txt
if errorlevel 1 (
    echo [ERROR] pip install failed. Check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo [2/3] Installing Playwright browser (Chromium, for web automation)...
playwright install chromium
if errorlevel 1 (
    echo [WARN] Playwright install failed - browser/web-automation mode won't work.
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
echo    Next step:
echo      Double-click start.bat to launch the floating capsule.
echo      On first run it will ask you to paste a free OpenRouter key
echo      (get one in ~30s at openrouter.ai/keys) - no .env editing needed.
echo.
echo      (Prefer the browser dashboard? Run start_web.bat instead.)
echo  ============================================
echo.
pause
