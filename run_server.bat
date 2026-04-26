@echo off
echo Starting AI Computer (web mode)...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
pause
