@echo off
cd /d "C:\Users\mohit\OneDrive\Desktop\Ai_computer\Ai_computer"
C:\Users\mohit\AppData\Local\Programs\Python\Python312\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
