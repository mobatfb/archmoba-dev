# VIRTUALEDUC v0.1.1

Sistema inicial de capacitaciones online en PHP nativo, sin frameworks ni Composer.

## Requisitos
- PHP 8.1 o superior con PDO MySQL y sesiones.
- MySQL o MariaDB.
- HTTPS en producción.

## Instalación
1. Copiar la carpeta VIRTUALEDUC al hosting.
2. Crear una base de datos y un usuario de base de datos con permisos sobre ella.
3. Importar schema.sql mediante phpMyAdmin.
4. Copiar config.example.php a config.local.php y completar DSN y credenciales. No publicar las credenciales en GitHub.
5. Desde la terminal del servidor, en la carpeta VIRTUALEDUC, ejecutar: php install.php. Introducir nombre, correo y una contraseña de 12 a 72 bytes. No se requiere token de instalación.
6. Abrir index.php e iniciar sesión con el administrador creado.
7. Configurar el servidor para impedir acceso HTTP a archivos de configuración, SQL, archivos ocultos y documentación. Desactivar display_errors en producción.

Si no tienes terminal en el hosting, ejecuta php install.php --sql en tu computadora con PHP instalado. Copia el INSERT generado y ejecútalo en la pestaña SQL de phpMyAdmin, dentro de virtualeduc. La contraseña se almacena mediante hash. Conserva privado el SQL generado.

## Actualización desde v0.1.0
Descomprimir el parche sobre la carpeta existente. No se requiere migración SQL. Eliminar la entrada antigua del token de config.local.php (ya no se utiliza). Si ya existe un administrador, puede ingresar con sus credenciales sin cambios. No se reemplaza config.local.php ni se eliminan datos.

## Funciones iniciales
Administrador: crea usuarios, cursos, lecciones, publica y matricula.
Docente: administra sus propios cursos y lecciones.
Estudiante: consulta sus cursos publicados y registra el avance.

## Pendientes
Evaluaciones, certificados, multimedia, edición y eliminación de registros, recuperación de contraseñas, informes, auditoría, límites de intentos de acceso robustos y pruebas de integración. No desplegar para usuarios reales sin validar seguridad y funcionamiento en el servidor de destino.

La interfaz está en index.php y la lógica compartida en app.php.
