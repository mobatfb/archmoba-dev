@echo off
setlocal
cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1
py -B KOF_Control.py
if errorlevel 1 (
  echo.
  echo Si falta PySide6, instalar una sola vez con:
  echo py -m pip install --no-cache-dir PySide6
  echo.
  pause
)
endlocal
