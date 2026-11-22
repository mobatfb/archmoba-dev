@echo off
cd /d "%~dp0"
where py.exe >nul 2>&1 || (echo ERROR: Instala Python 3 con tkinter para usar la interfaz.& pause & exit /b 1)
py -3 "%~dp0PYTHON\futureo_vjoy_manager.py"
pause