# VIRTUALEDUC v0.1.18

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
5. Importar el SQL privado de creación del administrador entregado por separado, mediante phpMyAdmin, usando la tabla users (si el archivo antiguo indica ve_users, reemplazar ese nombre por users). El repositorio público no contiene credenciales predeterminadas.
6. Abrir index.php e ingresar con el usuario admin o su correo interno admin@virtualeduc.local. Cambiar inmediatamente la contraseña inicial desde "Cambiar mi contraseña".
7. Configurar el servidor para impedir acceso HTTP a archivos de configuración, SQL, archivos ocultos y documentación. Desactivar display_errors en producción. Mantener el SQL de creación fuera del directorio público.

## Actualización desde v0.1.0 o v0.1.1
Descomprimir los archivos de VIRTUALEDUC del parche sobre la carpeta existente. No se requiere migración del esquema. El token ya no se utiliza. El instalador anterior queda deshabilitado. Si no existe un administrador, importar el SQL privado en phpMyAdmin después de importar schema.sql. Si ya existe un administrador, el SQL inicial no altera su cuenta. No se reemplaza config.local.php ni se eliminan datos.

## Actualización a v0.1.3
1. Hacer un respaldo de la base de datos.
2. Importar migrations/0.1.3.sql en phpMyAdmin sobre la base existente.
3. Copiar los archivos del parche sobre VIRTUALEDUC. No reemplazar config.local.php.
4. Iniciar sesión como administrador y crear subadministradores desde Administración > Crear usuario.

Menú lateral expandible por secciones, navegación adaptada al rol y diseño adaptable.
El subadministrador crea docentes y estudiantes, gestiona cursos y matrículas, pero no crea administradores ni subadministradores. Puede asignar un docente o a sí mismo como responsable de un curso. El docente gestiona solamente sus cursos; el estudiante accede a sus cursos publicados y su progreso.

## Actualización a v0.1.4
Copiar los archivos del parche sobre la instalación v0.1.3. No se requiere migración SQL nueva. Los cuatro roles tienen listados independientes según permisos. En usuarios, cursos, lecciones y matrículas, el botón Crear abre un diálogo Individual / Masivo (CSV). Descargar la plantilla de cada diálogo, completar las filas en UTF-8 con delimitador punto y coma y subirla. El máximo es de 100 usuarios o 500 registros de otros tipos por archivo, con tamaño máximo 2 MB (también sujeto a la configuración PHP). Las contraseñas deben tener de 12 a 72 bytes; conservar los CSV de usuarios en un lugar privado. La importación es transaccional: si existe un error no se guarda ningún registro. Los cursos de docentes se asignan automáticamente al docente autenticado; los responsables y estudiantes se identifican por correo, y las matrículas globales por ID de curso. No se reemplazan credenciales ni datos existentes.

## Actualización a v0.1.5
Corrección visual de contraste en todos los botones, enlaces de acción y pestañas de los diálogos. Se mantienen los formularios individuales, CSV y permisos. No requiere SQL. Aplicar sobre v0.1.4 y recargar la página.

## Actualización a v0.1.6
Diseño responsive mejorado en móviles, tabletas y escritorio. Menú lateral plegado por defecto hasta 900 px, formularios y diálogos adaptados a pantallas pequeñas, botones táctiles y tablas con desplazamiento horizontal local. Se conservan la creación individual y masiva, los permisos y los colores de los botones. Copiar el parche sobre v0.1.5; no requiere SQL.

## Actualización a v0.1.7
Aplicar este parche acumulativo sobre v0.1.5 o v0.1.6. No requiere SQL. Administración contiene únicamente Usuarios: una tabla, un botón Crear y una línea de recuentos según el alcance del rol. El formulario individual permite seleccionar el rol; la nueva plantilla CSV es nombre;correo;contrasena;rol. Descargar la plantilla nueva. Los subadministradores solo pueden crear y consultar docentes y estudiantes. Se conservan todos los permisos, diálogos y datos existentes.

## Actualización a v0.1.8
Copiar el parche sobre v0.1.7. Administración > Usuarios incluye búsqueda inmediata por nombre o correo, filtro por rol, contador de coincidencias y opción Limpiar. Los filtros se combinan y solo muestran usuarios que el perfil autenticado está autorizado a consultar. Sin JavaScript, el formulario permite aplicar los filtros mediante PHP. No requiere SQL.

## Actualización a v0.1.9
Resumen de Usuarios en el orden Estudiantes, Docentes, Subadministradores, Administradores y Total, con separadores visibles. El selector de roles usa el mismo orden y conserva los permisos existentes. Aplicar sobre v0.1.8; no requiere SQL.

## Actualización a v0.1.10
1. Hacer respaldo y ejecutar migrations/0.1.10.sql en phpMyAdmin.
2. Copiar el parche sobre v0.1.9, conservando config.local.php y archivos previos.
3. Como administrador abrir Configuración > Configuración institucional.
4. Guardar nombre, subtítulo, teléfono, correo, periodo activo y logo opcional.

El logo se guarda en uploads/institution/ con nombre aleatorio y extensión de imagen validada; MySQL solo almacena su ruta relativa. PHP necesita permiso de escritura en esa carpeta, fileinfo y límites de subida adecuados (2 MB por logo). El archivo .htaccess bloquea el acceso HTTP directo en Apache; para Nginx o servidores que ignoran .htaccess, bloquear acceso directo a /uploads/institution/ en la configuración del servidor. Las imágenes se sirven mediante index.php?institution_logo=1. No subir logos reales al repositorio. No se inventan datos de contacto ni periodo: se muestran los datos que el administrador configure. El menú conserva las funciones reales de VIRTUALEDUC; no se agregan módulos escolares sin implementar.

## Actualización a v0.1.11
Las plantillas CSV de usuarios, capacitaciones, lecciones y matrículas incluyen una fila de ejemplo adaptada a sus columnas. Reemplazar o eliminar la fila de ejemplo antes de importar. Aplicar sobre v0.1.10; no requiere SQL.

## Actualización a v0.1.12
Hacer un respaldo e importar migrations/0.1.12.sql una sola vez sobre v0.1.11 antes de copiar el parche. Se conservan los ID, cuentas, contraseñas y relaciones. El administrador inicial conserva admin; las cuentas antiguas conservan su correo como usuario y su nombre completo en Nombres hasta que se edite su identificación. La creación individual requiere usuario, nombres, apellidos, correo, contraseña y rol. El usuario admite letras, números, puntos, guiones y guion bajo; se guarda como texto. Se puede iniciar sesión por usuario o por correo. Los administradores y subadministradores pueden editar los datos de identidad de los usuarios que tienen autorizados.

Nuevas plantillas CSV (UTF-8, separador punto y coma):
- Usuarios: usuario;nombres;apellidos;correo;contrasena;rol
- Capacitaciones: titulo;descripcion;usuario_responsable (el docente solo puede usar su propio usuario).
- Matrículas generales: id_curso;usuario_estudiante. Desde un curso: usuario_estudiante.
- Lecciones: titulo;contenido (sin cambios).
Descargar las nuevas plantillas y reemplazar las filas de ejemplo. Si se usan identificadores numéricos con ceros iniciales en Excel, dar formato de texto a la columna antes de escribirlos. No publicar CSV con contraseñas.

## Actualización a v0.1.13
La creación individual y masiva admite contraseñas iniciales de al menos 8 caracteres (incluidos 8 dígitos) y máximo 72 bytes. Al cambiar su propia contraseña, el usuario debe elegir una nueva de al menos 8 caracteres, con mayúscula, minúscula, número y signo especial. Se valida en PHP y se mantiene el hash de contraseña. Se recomienda utilizar contraseñas iniciales únicas y cambiarlas cuanto antes. Aplicar sobre v0.1.12; no requiere SQL.

## Actualización a v0.1.14
La acción Editar de la tabla de Usuarios abre un diálogo independiente de Crear, con identificación precargada, rol informativo, Guardar cambios y Cancelar. Se conserva la autorización del servidor, el buscador y el filtro por roles. El formulario reutilizable se ubica en modules/user_edit.php. Todos los avisos de éxito, error y configuración incluyen un botón de cierre sin recargar la página. Aplicar sobre v0.1.13; no requiere SQL.

## Actualización a v0.1.15
Hacer un respaldo de la base de datos y detener temporalmente el acceso al sistema. Sobre v0.1.14, ejecutar una sola vez migrations/0.1.15.sql en phpMyAdmin, en la base de datos existente, y luego copiar el parche. Las seis tablas se renombran sin el prefijo ve_, conservando registros, ID y relaciones. Si ya existe una tabla de destino con el mismo nombre, no ejecutar la migración hasta resolver el conflicto. No importar schema.sql sobre una instalación anterior para realizar esta actualización. Las migraciones anteriores conservan sus nombres históricos y no deben ejecutarse nuevamente. Para una instalación nueva, usar directamente schema.sql actualizado y adaptar el SQL privado del administrador para que utilice users en lugar de ve_users.

## Actualización a v0.1.16
Respaldar la base de datos e importar migrations/0.1.16.sql sobre v0.1.15; copiar el parche directamente en la carpeta del sistema. La migración corrige el catálogo de roles y conserva los cuatro roles válidos. Las cuentas con un rol inválido quedan Sin rol asignado (unassigned, sin acceso). Como administrador, abrir Administración > Usuarios y usar Asignar rol en la cuenta afectada. No se conceden privilegios automáticamente. Se verifica que el rol de las nuevas cuentas se guarde correctamente antes de confirmar la creación. Los subadministradores conservan sus permisos anteriores.

## Actualización a v0.1.17
Perfil personal inspirado en el SGA: clic en el usuario del panel lateral para abrir un flotante, subir o eliminar la foto y consultar la cuenta. El módulo Mi cuenta conserva el cambio de contraseña. Todos los roles válidos pueden administrar únicamente su foto. Se aceptan JPG, PNG, GIF y WebP (hasta 5 MB, 12 megapíxeles) y se convierten a PNG de 120 × 120 con recorte centrado. Se muestran iniciales cuando no existe foto. La imagen se guarda por ID interno del usuario, en una carpeta privada .virtualeduc_private fuera de la raíz web, separada por instalación, sin guardar archivos ni rutas en MySQL. La descarga exige la sesión del propietario. PHP necesita GD y permisos para crear/escribir la carpeta privada; opcionalmente EXIF y mbstring. Si el hosting impide escribir fuera de la raíz web, no se subirá la foto: solicitar los permisos necesarios, nunca mover las imágenes a un directorio público. Los límites upload_max_filesize y post_max_size deben permitir la subida. Aplicar sobre v0.1.16; no requiere SQL. Incluir la carpeta privada en los respaldos del hosting.

## Actualización a v0.1.18
Parche acumulativo sobre v0.1.16: incluye el perfil con foto de v0.1.17 y permite modificar el rol desde Editar usuario. El administrador puede cambiar los roles de otras cuentas; el subadministrador puede editar y asignar únicamente Docente y Estudiante. No se permite cambiar el propio rol. Los cambios de rol conservan la identificación interna, la contraseña y las relaciones existentes y se aplican a partir de la siguiente solicitud. No requiere SQL si ya se aplicó migrations/0.1.16.sql.

## Arquitectura modular
- index.php: punto de entrada.
- app.php: configuración, sesión, seguridad, acceso a datos y roles.
- core/request.php: procesamiento de solicitudes y autorización.
- core/layout.php: estructura común de la página.
- panel.php: menú y enrutamiento por lista de módulos autorizados.
- modules/: un PHP por módulo visual (home, users, courses, course, enrollments, progress, account, login).
- create.php y create.js: servicio compartido para creación individual y CSV.
- responsive.css y responsive.js: adaptación a móviles y tabletas.

## Funciones iniciales
Administrador: crea usuarios de los cuatro roles, cursos, lecciones, publica y matricula.
Subadministrador: crea docentes y estudiantes y gestiona la operación académica.
Docente: administra sus propios cursos y lecciones.
Estudiante: consulta sus cursos publicados y registra el avance.

## Pendientes
Evaluaciones, certificados, multimedia, edición y eliminación de registros, recuperación de contraseñas, informes, auditoría, límites de intentos de acceso robustos y pruebas de integración. No desplegar para usuarios reales sin validar seguridad y funcionamiento en el servidor de destino.

La interfaz se divide en core/layout.php y modules/. La lógica compartida está en app.php y create.php.
