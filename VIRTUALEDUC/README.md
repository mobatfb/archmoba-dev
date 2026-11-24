# VIRTUALEDUC v0.1.0

Sistema inicial de capacitaciones online en PHP nativo, sin frameworks ni Composer.

## Requisitos
- PHP 8.1 o superior con PDO MySQL y sesiones.
- MySQL o MariaDB.
- HTTPS en producción.

## Instalación
1. Copiar la carpeta VIRTUALEDUC al hosting.
2. Crear una base de datos y un usuario de base de datos con permisos sobre ella.
3. Importar schema.sql mediante phpMyAdmin.
4. Copiar config.example.php a config.local.php, completar DSN y credenciales, y generar un token aleatorio de instalación de al menos 32 caracteres (por ejemplo: php -r "echo bin2hex(random_bytes(32));").
5. Abrir index.php y crear el primer administrador con el token y una contraseña de al menos 12 caracteres.
6. Eliminar el token de config.local.php después de instalar. No publicar las credenciales ni el token en GitHub.
7. Configurar el servidor para impedir acceso HTTP a archivos de configuración, SQL, archivos ocultos y documentación. Desactivar display_errors en producción.

## Funciones iniciales
Administrador: crea usuarios, cursos, lecciones, publica y matricula.
Docente: administra sus propios cursos y lecciones.
Estudiante: consulta sus cursos publicados y registra el avance.

## Pendientes
Evaluaciones, certificados, multimedia, edición y eliminación de registros, recuperación de contraseñas, informes, auditoría, límites de intentos de acceso robustos y pruebas de integración. No desplegar para usuarios reales sin validar seguridad y funcionamiento en el servidor de destino.

La interfaz está en index.php y la lógica compartida en app.php.
