@echo off
echo ===================================================
echo STARTING ISL FULL-STACK APPLICATION
echo Backend: FastAPI on http://localhost:8000
echo Frontend: Vite + React on http://localhost:5173
echo ===================================================

start "ISL Backend" cmd /k "cd /d "%~dp0app\backend" && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
start "ISL Frontend" cmd /k "cd /d "%~dp0app\frontend" && npm run dev"

echo Both services launched in separate windows.
echo Open http://localhost:5173 in your browser.
