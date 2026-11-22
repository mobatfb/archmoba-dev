@echo off
setlocal
title FUTUREO VJOY - PRUEBA DE MANDO P1
cd /d "%~dp0"
echo ====================================================
echo  FUTUREO VJOY1 - PRUEBA DE EJE X Y BOTON 1
echo  SOLO LABORATORIO, NO MODIFICA LA INSTALACION
echo ====================================================
echo.
if not exist "%~dp0PYTHON\futureo_vjoy.py" (
 echo ERROR: falta PYTHON\futureo_vjoy.py. Extrae el ZIP completo.
 pause
 exit /b 2
)
where py.exe >nul 2>&1
if errorlevel 1 (
 echo ERROR: no se encontro Python Launcher. Instala Python 3 para usar la prueba.
 pause
 exit /b 2
)
echo Se abrira el panel de mandos de Windows.
echo Selecciona el mando virtual, pulsa Propiedades y deja esa ventana visible.
start "" control.exe joy.cpl
echo.
echo El script esperara 5 segundos y enviara tres pulsaciones del boton 1
echo y movimientos del eje X. Despues centrara el mando.
echo.
pause
py -3 "%~dp0PYTHON\futureo_vjoy.py" --selftest
if errorlevel 1 (
 echo ERROR: fallo la prueba de protocolo Python.
 pause
 exit /b 1
)
py -3 "%~dp0PYTHON\futureo_vjoy.py" --demo 1
if errorlevel 1 (
 echo ERROR: no se pudo abrir o enviar informes a \\.\FUTJOY1.
 echo Comparte el mensaje completo; el controlador puede estar bloqueado.
 pause
 exit /b 1
)
echo.
echo Prueba enviada. Confirma si viste el eje X y el boton 1 moverse.
pause
endlocal
