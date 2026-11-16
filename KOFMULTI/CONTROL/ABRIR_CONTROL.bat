@echo off
rem KOFMULTI CONTROL v.0.0.2 — inicia GUI sin consola Python.
rem Este .bat puede mostrar una ventana CMD brevemente.
rem Para cero ventanas CMD usar ABRIR_CONTROL_SIN_CONSOLA.vbs o KOF_Control.pyw.
cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1
wscript.exe //nologo "%~dp0ABRIR_CONTROL_SIN_CONSOLA.vbs"
exit /b
