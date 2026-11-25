# FUTUREO STUDIO v0.1.1

Requisitos: PHP 7.4 o superior (recomendado PHP 8.3+), sin base de datos ni dependencias externas. Extrae el ZIP en una carpeta de tu hosting PHP, con permiso de escritura para `proyectos/`. Abre `index.php` para la vista pública y `admin.php` para administrar.

Usuario inicial: `admin`. Contraseña inicial de pruebas: `12345678`. El repositorio es público: antes de publicar en Internet, define la variable de entorno `FUTUREO_ADMIN_PASSWORD` con una contraseña propia y utiliza HTTPS. Si tu hosting no permite variables de entorno, cambia la contraseña predeterminada en `studio.php` en tu copia privada. Nunca subas la contraseña real al repositorio público.

Los proyectos son archivos JSON con extensión `.fprj` almacenados en el disco del servidor, no en el navegador. Se nombran con la fecha local de Ecuador y un sufijo numérico si ya existe el nombre. El botón Nuevo crea el proyecto y abre un espacio de trabajo vacío. El índice público muestra todos los proyectos, incluidos los temporales; no permite crear ni editar.

Apache: `proyectos/.htaccess` impide acceso directo y listado de archivos si AllowOverride lo permite. En Nginx u otro servidor configura una regla equivalente para bloquear URLs directas a proyectos/; las páginas PHP continuarán funcionando. Para una prueba local: `php -S 127.0.0.1:8080` (no usar ese servidor en producción). Conserva `proyectos/` al actualizar la aplicación y realiza respaldos de sus archivos.

## Actualización v0.1.1

Si actualizas desde v0.1.0, elimina manualmente las carpetas vacías `AUDIO/`, `VIDEO/`, `IMAGE/`, `LIVE/` y `GAMING/` del directorio de FUTUREO STUDIO. Comprueba antes que no contengan archivos propios; el ZIP no elimina carpetas existentes. No borres `proyectos/`. No hay cambios en el código PHP.
