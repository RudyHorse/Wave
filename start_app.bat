@echo off
setlocal

set BACKEND_PORT=8010
set FRONTEND_PORT=5173

echo ==============================================
echo    SeisViz - Seismic Data Visualization
echo ==============================================
echo.
echo First-time setup (run once if needed):
echo    backend : pip install -r requirements.txt
echo    frontend: npm install
echo.

REM Stop a stale Wave backend from a previous run (leftover on our port).
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%BACKEND_PORT%" ^| findstr "LISTENING"') do (
    echo Stopping previous Wave backend process %%a ...
    taskkill /F /PID %%a >nul 2>&1
)

echo Starting backend  on http://localhost:%BACKEND_PORT% ...
start "Wave Backend" /D "%~dp0backend" cmd /k "python -m uvicorn main:app --reload --port %BACKEND_PORT%"

echo Starting frontend on http://localhost:%FRONTEND_PORT% ...
start "Wave Frontend" /D "%~dp0frontend" cmd /k "npm run dev"

echo.
echo ==============================================
echo   Backend  : http://localhost:%BACKEND_PORT%
echo   Frontend : http://localhost:%FRONTEND_PORT%
echo ==============================================
echo.
echo Open http://localhost:%FRONTEND_PORT% in your browser.
echo Close the backend/frontend windows to stop the app.
echo.
pause

endlocal
