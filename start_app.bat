@echo off
setlocal

echo ==============================================
echo    SeisViz - Seismic Data Visualization
echo ==============================================
echo.
echo First-time setup (run once if needed):
echo    backend : pip install -r requirements.txt
echo    frontend: npm install
echo.
echo Starting backend  on http://localhost:8000 ...
start "SeisViz Backend" /D "%~dp0backend" cmd /k "python -m uvicorn main:app --reload --port 8000"

echo Starting frontend on http://localhost:5173 ...
start "SeisViz Frontend" /D "%~dp0frontend" cmd /k "npm run dev"

echo.
echo ==============================================
echo   Backend  : http://localhost:8000
echo   Frontend : http://localhost:5173
echo ==============================================
echo.
echo Open http://localhost:5173 in your browser.
echo Close the backend/frontend windows to stop the app.
echo.
pause

endlocal
