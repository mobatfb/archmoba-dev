# VIRTUALEDUC v0.1.2

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
5. Importar el SQL privado de creación del administrador entregado por separado, mediante phpMyAdmin. El repositorio público no contiene credenciales predeterminadas.
6. Abrir index.php e ingresar con el usuario admin o su correo interno admin@virtualeduc.local. Cambiar inmediatamente la contraseña inicial desde "Cambiar mi contraseña".
7. Configurar el servidor para impedir acceso HTTP a archivos de configuración, SQL, archivos ocultos y documentación. Desactivar display_errors en producción. Mantener el SQL de creación fuera del directorio público.

## Actualización desde v0.1.0 o v0.1.1
Descomprimir los archivos de VIRTUALEDUC del parche sobre la carpeta existente. No se requiere migración del esquema. El token ya no se utiliza. El instalador anterior queda deshabilitado. Si no existe un administrador, importar el SQL privado en phpMyAdmin después de importar schema.sql. Si ya existe un administrador, el SQL inicial no altera su cuenta. No se reemplaza config.local.php ni se eliminan datos.

## Funciones iniciales
Administrador: crea usuarios, cursos, lecciones, publica y matricula.
Docente: administra sus propios cursos y lecciones.
Estudiante: consulta sus cursos publicados y registra el avance.

## Pendientes
Evaluaciones, certificados, multimedia, edición y eliminación de registros, recuperación de contraseñas, informes, auditoría, límites de intentos de acceso robustos y pruebas de integración. No desplegar para usuarios reales sin validar seguridad y funcionamiento en el servidor de destino.

La interfaz está en index.php y la lógica compartida en app.php.
