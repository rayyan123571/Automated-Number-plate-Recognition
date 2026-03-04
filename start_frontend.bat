@echo off
echo ========================================
echo Starting ANPR Frontend Server
echo ========================================

cd /d "%~dp0frontend"

echo Installing dependencies...
call npm install --silent

echo.
echo Starting Next.js on http://localhost:3000
echo.
npm run dev

pause
