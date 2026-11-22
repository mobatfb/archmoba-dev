@echo off
title FUTUREO VJOY - DIAGNOSTICO CERTIFICADO (LECTURA)
cd /d "%~dp0"
echo Este diagnostico no instala ni cambia certificados.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0HERRAMIENTAS\instalador.ps1" -Accion DiagnosticarCert
if errorlevel 1 echo ERROR: Revisa las indicaciones anteriores.
pause
