@echo off
REM Check if the container exists and start it if it does
docker ps -a -q -f name=redis-instance >nul 2>&1
if %errorlevel% == 0 (
    echo Starting existing redis-instance container...
    docker start redis-instance
) else (
    echo Running a new Redis container...
    docker run --name redis-instance -d -p 6379:6379 redis
)

REM Activate the virtual environment
call venv\Scripts\activate.bat

timeout /t 3 /nobreak >nul

echo Starting Celery worker...
start "Celery Worker" cmd /k "celery -A api.celery worker --pool=gevent --loglevel=INFO"

timeout /t 2 /nobreak >nul

echo Starting Celery Beat...
start "Celery Beat" cmd /k "celery -A api.celery beat --loglevel=INFO"

echo.
echo ==========================================
echo Celery worker and Beat are running in separate windows
echo Close the windows to stop the processes
echo ==========================================
echo.

pause

