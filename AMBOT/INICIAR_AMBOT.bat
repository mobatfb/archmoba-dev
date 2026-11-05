@echo off
setlocal
cd /d "%~dp0"
title AMBOT - ARCHMOBA ROBOTICS
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 app.py
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    python app.py
  ) else (
    echo Instala Python 3.9 o superior.
  )
)
pause
