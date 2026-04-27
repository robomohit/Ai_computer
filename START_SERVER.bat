@echo off
echo ==========================================
echo Starting AI Computer Application...
echo ==========================================
echo.
echo Access the app at: http://localhost:8080
echo Press Ctrl+C to stop the server
echo.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
pause
