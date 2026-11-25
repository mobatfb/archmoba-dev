@echo off
setlocal
cd /d "%~dp0"
set "PHP_BIN="
where php >nul 2>nul && set "PHP_BIN=php"
if not defined PHP_BIN if exist "C:\xampp\php\php.exe" set "PHP_BIN=C:\xampp\php\php.exe"
if not defined PHP_BIN if exist "C:\laragon\bin\php" for /d %%D in ("C:\laragon\bin\php\*") do if exist "%%~fD\php.exe" set "PHP_BIN=%%~fD\php.exe"
if not defined PHP_BIN (
  echo No se encontro PHP. Instala PHP 8.1+ o XAMPP y agrega PHP al PATH.
  pause
  exit /b 1
)
echo Sorteo Studio v0.2.0 - entorno local
"%PHP_BIN%" -v
 echo Verifica que MySQL este iniciado y que hayas importado database\sorteos_studio.sql.
 "%PHP_BIN%" -r "exit(in_array('mysql', PDO::getAvailableDrivers(), true)?0:1);"
 if errorlevel 1 (
   echo Activa pdo_mysql en php.ini y vuelve a iniciar.
   pause
   exit /b 1
 )
 echo Abre http://127.0.0.1:8000 en tu navegador.
 echo Para detener el servidor, presiona Ctrl+C.
"%PHP_BIN%" -d upload_max_filesize=5M -d post_max_size=20M -S 127.0.0.1:8000 -t public
pause
