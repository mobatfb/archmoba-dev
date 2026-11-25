# Sorteo Studio v0.2.0 | MySQL / Hosting

Panel administrativo de pruebas con almacenamiento MySQL. No es una plataforma publica de rifas lista para produccion.

## 1. Crear e importar la base en cPanel / phpMyAdmin

1. En cPanel, abre Bases de datos MySQL (o Database Wizard). Crea una base, por ejemplo `sorteos` y un usuario dedicado, por ejemplo `sorteosuser`, con una contrasena fuerte. Anota los nombres completos con prefijo de tu hosting.
2. Asigna el usuario a la base y concede los permisos necesarios para crear tablas e indices e insertar, seleccionar, actualizar y eliminar registros. Para importar, utiliza los permisos que requiera tu proveedor; luego limita los permisos de la cuenta de la aplicacion a SELECT, INSERT, UPDATE y DELETE.
3. Abre phpMyAdmin y selecciona la base vacia recien creada. En Importar, elige `database/sorteos_studio.sql` y ejecuta. No hay CREATE DATABASE, USE, GRANT ni DEFINER fijo. El esquema requiere MySQL 8.0.16+ o MariaDB 10.4+, InnoDB y utf8mb4. No se instalan datos ficticios ni se borran tablas.
4. Opcional: importa `database/ingresos_vista_opcional.sql` si deseas consultar una vista de ingresos en phpMyAdmin y tienes permiso CREATE VIEW. El panel no la necesita.
5. Edita `config.php` con host, puerto, nombre completo de base, usuario y contrasena de tu proveedor. Nunca compartas la configuracion con credenciales ni la publiques en Git.

## 2. Instalacion de pruebas en hosting

- Requisitos: PHP 8.1+ (64 bits recomendado), PDO con pdo_mysql, Fileinfo, sesiones, HTTPS, permisos de escritura en `storage/uploads/`, y MySQL/MariaDB segun el apartado anterior.
- Puedes subir el contenido de SORTEOWEB a `public_html/sorteos/` y abrir `/sorteos/` directamente: el `index.php` de raiz carga el panel. Conserva todos los archivos ocultos `.htaccess`; Apache 2.4 debe permitir sus directivas y bloquear acceso directo a configuracion, SQL y storage. Si no puedes confirmar estos bloqueos, utiliza un DocumentRoot apuntando exclusivamente a `public/`.
- En cPanel, activa Privacidad del directorio (Directory Privacy) para la carpeta de instalacion (o `public/` si es el DocumentRoot) y crea un usuario con contrasena fuerte. Activa HTTPS y comprueba que el servidor entrega REMOTE_USER (o REDIRECT_REMOTE_USER) a PHP. El panel rechaza solicitudes remotas si no detecta HTTPS y autenticacion del servidor; no desactives esta comprobacion para publicar el panel.
- Si el hosting no permite configurar la raiz publica o no proporciona esas variables a PHP, utiliza solo el SQL y prueba el panel localmente hasta incorporar autenticacion nativa. No se garantiza compatibilidad con todos los hostings o configuraciones de proxy.
- Configura `upload_max_filesize=5M` y `post_max_size=20M` o superiores para permitir tres fotos de 5 MB. No otorgues permisos 777.
- Comprueba en una ventana privada que no puedes acceder sin autenticarte, ni descargar configuracion, SQL o fotos privadas. Guarda respaldos de MySQL y `storage/`.

## 3. Pruebas locales

Crea una base vacia `sorteos_studio` con phpMyAdmin o MySQL e importa el mismo SQL. Ajusta `config.php` al usuario local (preferiblemente no root). Ejecuta `INICIAR_WINDOWS.bat` o:

```sh
php -d upload_max_filesize=5M -d post_max_size=20M -S 127.0.0.1:8000 -t public
```

Abre http://127.0.0.1:8000. El panel permite solicitudes de loopback para desarrollo. No vincular a 0.0.0.0 ni exponer el servidor PHP de pruebas a Internet.

## 4. Migracion opcional de v0.1.0

Si tienes datos previos, detiene el panel anterior y respalda toda su carpeta storage. Con la base nueva vacia y config.php configurado, ejecuta desde terminal:

```sh
php migrate_json.php /ruta/a/SorteosPHP_v0.1.0/storage/data.json
```

El script importa sorteos, participaciones y copia fotos desde uploads sin sobreescribirlas. No hace falta si empiezas desde cero. Si no tienes terminal en tu hosting puedes ejecutar la migracion desde una copia local con acceso autorizado a la base de destino. El script es solo CLI. No se ha probado contra un servidor MySQL real en este entorno.

## 5. Alcance

- Sorteos: crear, editar, buscar, filtrar, activar y finalizar. Tres fotos; producto o dinero; cantidad y valor de boletos. No reabre finalizados.
- Participantes: listado por sorteo, nombre, correo, telefono, numero y estado de pago. Una fila por boleto. Restriccion UNIQUE evita repetir numero dentro de un sorteo.
- Ingresos: suma de boletos pagados y pendientes; precios almacenados en centavos de dolar.
- Ganadores: lista de sorteos finalizados. Las tablas raffle_evidence y winners reservan la estructura de la futura gestion del ZIP y resultado, pero la interfaz de carga/revelacion/reclamo todavia no existe. No se almacena la contrasena del ZIP ni se genera el ganador.
- Admins: tabla reservada para futura autenticacion nativa. Para las pruebas remotas la autenticacion depende del servidor web. La bitacora registra cambios de sorteos y participaciones, sin identificar aun al administrador.
- Se mantiene el modelo de carga de todos los registros y bloqueo global de escrituras del prototipo; sera necesario paginar y optimizar antes de operar con muchos usuarios simultaneos.
- La base de datos no garantiza la imparcialidad de un ganador seleccionado manualmente. La evidencia debe comprometerse antes de abrir el sorteo y publicarse de forma independiente. El codigo de reclamo visible en el PDF no basta para acreditar titularidad.

## Verificacion

Archivos PHP revisados con php -l. Este entorno no incluye servidor MySQL/MariaDB ni el controlador pdo_mysql, por lo que no se ha ejecutado la importacion ni probado el flujo contra una base real. Validar en una base vacia antes de usar datos reales. No conectar pagos reales ni abrir inscripciones publicas con esta version.
