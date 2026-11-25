# SORTEOWEB v1.0.1 | Base existente

Versión PHP modular estilo VIRTUALEDUC. Compatible con la base de ocho tablas originales: admins, app_lock, audit_events, participants, raffles, raffle_evidence, raffle_photos y winners. No utiliza tablas sw_.

## Instalación

1. Respaldar la base y la carpeta de la aplicación anterior. No borrar la base. Extraer el ZIP sin carpeta contenedora, conservar .htaccess y storage/uploads si existen fotos antiguas. No mezclar con versiones anteriores.
2. Seleccionar la base existente en phpMyAdmin e importar `actualizar_bd.sql`. Este parche MariaDB es repetible: añade must_change_password a admins, mime/content a raffle_photos y crea login_limits. No restablece claves ni borra registros. No importar el schema.sql de versiones anteriores.
3. Completar config.php (o config.local.php con prioridad) con usuario y contraseña MySQL reales; nunca publicar credenciales. La cuenta admin existente se conserva. Se requiere cambiar la clave temporal en el primer ingreso tras el parche.
4. Abrir index.php mediante HTTPS. El acceso no requiere privacidad de directorio de cPanel. Eliminar el SQL del directorio web tras importar. Comprobar las protecciones de Apache 2.4 (.htaccess) o equivalentes.

## Requisitos y alcance

PHP 8.1+ de 64 bits, PDO MySQL, Fileinfo, sesiones, MariaDB 10.4+ (diseñado para 11.4), Apache 2.4, HTTPS para acceso remoto. Fotos JPG/PNG/WebP hasta 2 MB por archivo, almacenadas en MySQL; configurar upload_max_filesize >= 2M, post_max_size >= 8M, max_allowed_packet >= 8M. Las fotos existentes con nombre válido y archivo conservado en storage/uploads se sirven por PHP. Los ingresos se calculan usando el precio inmutable del sorteo desde su activación. No conecta pagos reales. El ZIP ganador, su revelación y reclamo todavía no se implementan; se mantienen las tablas existentes para ese fin.

Los identificadores de sorteos y participantes conservan el formato hexadecimal de 24 caracteres. La auditoría usa audit_events y las operaciones se serializan por fila de sorteo; el índice único existente impide duplicados. El parche no migra tablas sw_ de otras instalaciones.

Pruebas locales: php -S 127.0.0.1:8000 (solo loopback). El servidor PHP no aplica .htaccess. No exponer a Internet. Validar la conexión y el flujo real en hosting antes de cargar datos reales. Se comprobó sintaxis PHP/JS; el entorno de desarrollo no dispone del servidor ni controlador PDO MySQL.
