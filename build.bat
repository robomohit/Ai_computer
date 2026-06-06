@echo off
setlocal

echo.
echo  ============================================
echo    Kynvoq - Build a distributable app
echo  ============================================
echo.
echo  This packages the app into dist\Kynvoq\ so you can share a runnable
echo  Windows desktop bundle.
echo.

:: Make sure PyInstaller is available
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [1/2] Installing build tools (PyInstaller)...
    python -m pip install -r requirements-build.txt
    if errorlevel 1 (
        echo [ERROR] Could not install PyInstaller. Check your internet connection.
        pause
        exit /b 1
    )
)

echo [2/2] Building (this can take a few minutes the first time)...
python -m PyInstaller Kynvoq.spec --noconfirm --clean
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. See the output above.
    pause
    exit /b 1
)

echo.
echo  ============================================
echo    Build complete!
echo.
echo    Your app is here:
echo      dist\Kynvoq\Kynvoq.exe
echo.
echo    Share the whole "dist\Kynvoq" folder, or wrap it into a single
echo    installer with Inno Setup / NSIS (see PACKAGING.md).
echo  ============================================
echo.
pause
