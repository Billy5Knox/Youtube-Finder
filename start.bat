@echo off
title YouTube Finder

echo ========================================
echo   YouTube Finder - Starting...
echo ========================================
echo.

:: Start backend
echo [1/3] Starting backend server...
cd /d "%~dp0backend"
start "YouTube Finder - Backend" cmd /k "uvicorn app.main:app --reload"

:: Wait for backend to be ready
echo [2/3] Waiting for backend to be ready...
:wait_backend
timeout /t 1 /nobreak >nul
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 goto wait_backend
echo       Backend is ready!

:: Start frontend
echo [3/3] Starting frontend...
cd /d "%~dp0frontend"
start "YouTube Finder - Frontend" cmd /k "npm run dev"

:: Wait for frontend to be ready
:wait_frontend
timeout /t 1 /nobreak >nul
curl -s http://localhost:5173 >nul 2>&1
if errorlevel 1 goto wait_frontend
echo       Frontend is ready!

echo.
echo ========================================
echo   YouTube Finder is running!
echo   Opening browser...
echo ========================================
echo.
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000
echo.
echo   Close the backend and frontend windows to stop.
echo ========================================

:: Open browser
start http://localhost:5173

exit
