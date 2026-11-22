@echo off
title FUTUREO VJOY - LABORATORIO
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0HERRAMIENTAS\instalador.ps1" -Accion ModoNormal
if errorlevel 1 echo ERROR: Revisa las indicaciones anteriores.
pause