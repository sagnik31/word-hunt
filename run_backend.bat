cd /d "%~dp0"
.venv\Scripts\python.exe -m uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000
pause
