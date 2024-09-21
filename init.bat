@echo off

@REM :: Install Python requirements
@REM pip install -r requirements.txt

@REM :: Install npm packages
@REM cd streaming
@REM npm install
@REM cd ..

:: Run Django server in one terminal
start cmd /k "python manage.py runserver"

:: Run streaming script in another terminal
start cmd /k "python streaming\main.py"
