@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE="
where python >nul 2>nul
if "%ERRORLEVEL%"=="0" set "PYTHON_EXE=python"

if "%PYTHON_EXE%"=="" (
    where py >nul 2>nul
    if "%ERRORLEVEL%"=="0" set "PYTHON_EXE=py -3"
)

if "%PYTHON_EXE%"=="" (
    echo Python was not found in PATH.
    echo Install Python 3 or run fixik.py with your own Python interpreter.
    echo.
    pause
    exit /b 1
)

if "%~1"=="" (
    %PYTHON_EXE% "%~dp0fixik.py"
) else (
    %PYTHON_EXE% "%~dp0fixik.py" %*
    echo.
    pause
)
