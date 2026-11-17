@echo off
title K2 Plus 3MF Studio Translator
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" app.py %*
) else (
    python app.py %*
)
if errorlevel 1 (
    echo.
    echo An error occurred. Press any key to exit.
    pause >nul
)
