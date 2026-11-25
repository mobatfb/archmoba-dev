# SGA UNEDID — V6

Sistema de Gestión Académica de la Unidad Educativa de Iniciación y Desarrollo Deportivo del Azuay. Versión consolidada: 24/11/2026.

## Contenido

- Proyecto base `SGA 23-11.zip`.
- V3 completa: evaluación cualitativa por aula (docente único), permisos administrativos y de jornada.
- V4: ejes agrupados en informe de aprendizaje PDF.
- V5: cabeceras agrupadas en la tabla de calificaciones.
- V6: nueva escala de resultados cualitativos, exportaciones y certificados.

## Instalación y actualización

1. Usar PHP 8.x con mysqli, mbstring, zip, dom, fileinfo y MySQL/MariaDB.
2. Conservar `config/database.php` y `config/recuperacion.php` de la instalación existente. Para una instalación nueva, copiar los archivos `config/database.example.php` y `config/recuperacion.example.php` a esos nombres y completar los valores en el servidor (o definir las variables de entorno correspondientes). Generar un secreto de recuperación único y configurarlo antes de habilitar el correo.
3. Utilizar una base de datos SGA existente o restaurar un respaldo del esquema inicial. Este repositorio incluye migraciones SQL, **no** un volcado inicial completo ni datos de producción. No ejecutar indiscriminadamente las migraciones.
4. Si se actualiza desde antes de V2/V3, revisar `sql/SQL_SGA_EVALUACION_CUALITATIVA_POR_AULA.sql` y `LEEME_EVALUACION_CUALITATIVA_PARAMETROS.txt`. V4–V6 no requieren migraciones adicionales.
5. Configurar el sitio y comprobar accesos según roles. Mantener los archivos de diagnóstico deshabilitados salvo durante mantenimiento controlado.

## Pruebas locales

```sh
php tests/pruebas_integridad.php
php tests/pruebas_excel.php
php tests/pruebas_parametros_aula.php
php tests/pruebas_resultados_cualitativos.php
```

## Seguridad

No versionar contraseñas, tokens, registros de errores, copias de la base de datos, archivos de estudiantes ni datos personales. Las plantillas de usuarios y representantes contienen solo ejemplos ficticios. Las credenciales de producción se configuran únicamente en el servidor.
