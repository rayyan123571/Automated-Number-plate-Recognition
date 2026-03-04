@echo off
echo ========================================
echo Starting ANPR Backend Server
echo ========================================

cd /d "%~dp0backend"

echo.
echo Starting server on http://localhost:8000
echo Docs available at: http://localhost:8000/docs
echo.
echo (Press Ctrl+C to stop)
echo.
venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
