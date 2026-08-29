@echo off
chcp 65001 >nul
title English Lady - Server
color 0B

echo ==========================================
echo    English Lady - Starting...
echo ==========================================
echo.

cd /d "%~dp0python\EnglishWoman"

REM --- 1) check python ---
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found! Install it from python.org and check "Add to PATH".
    pause
    exit /b 1
)

REM --- 2) install requirements (fast if already installed) ---
echo [1/4] Checking requirements...
python -m pip install -r ..\requirements.txt --quiet --disable-pip-version-check

REM --- 3) check and apply migrations ---
echo [2/4] Checking migrations...
python manage.py makemigrations --noinput
python manage.py migrate --noinput

REM --- 4) free port 8000 if something is using it ---
echo [3/4] Checking port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo     Port 8000 busy - closing process %%a ...
    taskkill /F /PID %%a >nul 2>nul
)

REM --- 5) open browser and run server ---
echo [4/4] Starting server...
echo.
echo    Site : http://127.0.0.1:8000
echo    Admin: http://127.0.0.1:8000/admin/
echo.
echo    (Close this window or press Ctrl+C to stop)
echo ==========================================
start "" http://127.0.0.1:8000
python manage.py runserver 8000

pause
