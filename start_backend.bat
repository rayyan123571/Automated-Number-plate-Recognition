@echo off
echo ========================================
echo Starting ANPR Backend Server
echo ========================================

:: Change to the backend directory
cd /d "%~dp0backend"

:: Define the python executable from the venv in the root directory
set PYTHON_EXE=..\venv\Scripts\python.exe

echo.
echo Starting server on http://localhost:8000
echo Docs available at: http://localhost:8000/docs
echo.
echo (Press Ctrl+C to stop)
echo.

if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) else (
    echo [ERROR] Virtual environment not found at %PYTHON_EXE%
    echo Please ensure the 'venv' folder exists in the project root.
    echo.
    echo Attempting to start with system python...
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
)

pause
