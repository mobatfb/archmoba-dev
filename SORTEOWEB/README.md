# SORTEOWEB 1.0.0

Reescritura del panel administrativo en PHP y MySQL, inspirada en la estructura modular de VIRTUALEDUC. Sin frameworks ni Composer; index.php en la raiz. No necesita una carpeta public/ ni la autenticacion de cPanel.

## Instalacion en hosting

1. Respaldar la instalacion anterior y sus datos. Vaciar solo la carpeta de esta aplicacion (no todo public_html), o instalar en una carpeta nueva. Extraer el ZIP directamente. Conservar los archivos ocultos .htaccess. No mezclar archivos antiguos con los nuevos.
2. Crear o seleccionar una base MySQL/MariaDB en cPanel. Importar `schema.sql` desde phpMyAdmin. El esquema usa tablas nuevas con prefijo `sw_`, no borra ni migra las anteriores.
3. Editar `config.php` con el nombre completo de la base y usuario, host, puerto y contrasena. Alternativamente copiarlo a `config.local.php` (tiene prioridad y esta ignorado en Git).
4. Importar `crear_admin.sql`, entregado por separado y en el ZIP privado. No esta en el repositorio publico. El usuario inicial es admin. La contrasena temporal de pruebas es 12345678 y debe cambiarse al primer ingreso. El SQL no reemplaza cuentas existentes. Retirar los SQL del directorio web al terminar.
5. Abrir https://tu-dominio/ruta/index.php. PHP gestiona las sesiones y el inicio de sesion. No necesita activar Privacidad del directorio de cPanel. HTTPS es obligatorio para un hosting; HTTP se permite solo para pruebas de loopback.

## Requisitos

PHP 8.1+ de 64 bits, PDO MySQL, Fileinfo, sesiones, Apache 2.4 con .htaccess o protecciones equivalentes, MySQL 8.0.16+ o MariaDB 10.4+. `upload_max_filesize` de al menos 2M, `post_max_size` de al menos 8M, `max_allowed_packet` de al menos 8M. Las fotos se almacenan en MySQL; considerar el espacio de la base y sus respaldos. Nunca publicar credenciales reales en Git.

## Funciones

- Sorteos: tabla, filtro por estado, busqueda, alta/edicion en modal, tres fotos, tipo producto/dinero, cantidad de boletos y valor. Alta como borrador. Solo los borradores se editan/eliminan; los activos se finalizan sin reapertura.
- Participantes: seleccion de sorteo, listado por numero, nombre, correo, telefono, registro y edicion, pago pendiente/pagado. Solo sorteos activos admiten registros; no se puede repetir el numero. Los boletos pagados no se pueden liberar ni cambiar de numero o volver a pendientes.
- Ingresos: confirmados y pendientes, potencial; no hay pasarela ni conciliacion bancaria.
- Ganadores: consulta de sorteos finalizados y estructura SQL para evidencia y resultado. Todavia no se implementa carga/revelacion del ZIP, ni la seleccion o reclamo del ganador.
- Cuenta: login propio, bcrypt, cambio de contrasena, cierre de sesion, bloqueo de intentos en base de datos, CSRF, PDO preparado, bloqueo por sorteo en transacciones, auditoria de acciones.

## Pruebas locales

Con MySQL configurado, ejecutar `php -S 127.0.0.1:8000` en la carpeta del proyecto y abrir `http://127.0.0.1:8000/`. El servidor incorporado no aplica .htaccess: usar solo en loopback, no exponer a Internet. En hosting comprobar que /config.php, /schema.sql y /modules/ no son accesibles. No abrir inscripciones ni pagos reales con esta version de pruebas.

La verificacion de sintaxis PHP y JavaScript y las pruebas de renderizado con datos simulados no sustituyen una prueba con MySQL real. Esta version no se ha probado en el hosting del usuario.
