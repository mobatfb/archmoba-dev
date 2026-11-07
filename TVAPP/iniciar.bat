@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHON_EXE="

for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%I"
if not defined PYTHON_EXE for /f "delims=" %%I in ('python -c "import sys; print(sys.executable) if sys.version_info.major == 3 else None" 2^>nul') do set "PYTHON_EXE=%%I"

if not defined PYTHON_EXE (
    echo No se encontro Python 3. Instalando Python 3.13 con winget...
    where winget >nul 2>&1
    if errorlevel 1 (
        echo No se encontro winget. Instala Python desde https://www.python.org/downloads/windows/
        pause
        exit /b 1
    )
    winget install --id Python.Python.3.13 --exact --source winget --scope user --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo La instalacion automatica fallo o fue cancelada.
        pause
        exit /b 1
    )
    for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%I"
    if not defined PYTHON_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    if not defined PYTHON_EXE for /f "delims=" %%I in ('python -c "import sys; print(sys.executable) if sys.version_info.major == 3 else None" 2^>nul') do set "PYTHON_EXE=%%I"
)

if not defined PYTHON_EXE (
    echo Python parece estar instalado, pero aun no esta accesible.
    echo Cierra esta ventana y vuelve a abrir iniciar.bat.
    pause
    exit /b 1
)

"%PYTHON_EXE%" "%~dp0app.py"
if errorlevel 1 pause
endlocal
