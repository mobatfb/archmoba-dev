-- SGA UNEDID | Jornadas de areas guardadas en un solo CAMPO (sin tabla nueva)
-- Respaldar la base de datos antes de ejecutar en phpMyAdmin.
-- Compatible con instalaciones que ya aplicaron la version anterior area_jornadas.
-- El script se puede ejecutar de nuevo; no reemplaza valores ya configurados.

-- 1. Agregar el campo solo si no existe (MySQL/MariaDB).
SET @sga_col_existe := (
    SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='areas' AND column_name='jornadas_ids'
);
SET @sga_sql := IF(@sga_col_existe=0,
    'ALTER TABLE `areas` ADD COLUMN `jornadas_ids` VARCHAR(512) NULL DEFAULT NULL',
    'SELECT ''El campo areas.jornadas_ids ya existe'' AS estado');
PREPARE sga_cmd FROM @sga_sql; EXECUTE sga_cmd; DEALLOCATE PREPARE sga_cmd;

-- 2. Si ya instalaste el parche con tabla area_jornadas, COPIAR las asociaciones
--    al nuevo campo, respetando las selecciones realizadas anteriormente.
--    La tabla anterior NO se borra por precaucion, pero dejara de utilizarse.
SET @sga_tabla_anterior := (
    SELECT COUNT(*) FROM information_schema.tables
    WHERE table_schema=DATABASE() AND table_name='area_jornadas'
);
SET @sga_sql := IF(@sga_tabla_anterior>0,
    'UPDATE `areas` a JOIN (SELECT `area_id`, GROUP_CONCAT(`jornada_id` ORDER BY `jornada_id` SEPARATOR '','') AS ids FROM `area_jornadas` GROUP BY `area_id`) v ON v.area_id=a.id SET a.jornadas_ids=v.ids WHERE a.jornadas_ids IS NULL OR a.jornadas_ids=''''',
    'SELECT ''Sin tabla anterior: no se necesita migrar'' AS estado');
PREPARE sga_cmd FROM @sga_sql; EXECUTE sga_cmd; DEALLOCATE PREPARE sga_cmd;

-- 3. Areas existentes SIN jornada: mantener disponibilidad en las jornadas activas.
UPDATE `areas` a
SET a.jornadas_ids = (
    SELECT GROUP_CONCAT(j.id ORDER BY j.orden, j.id SEPARATOR ',')
    FROM `jornadas` j WHERE j.activo=1
)
WHERE a.archivado_en IS NULL AND (a.jornadas_ids IS NULL OR a.jornadas_ids='');

-- 4. Mostrar resultado de control.
SELECT a.id, a.codigo, a.nombre, a.jornadas_ids,
       (SELECT GROUP_CONCAT(j.nombre ORDER BY j.orden SEPARATOR ' | ')
          FROM jornadas j WHERE FIND_IN_SET(j.id, a.jornadas_ids)>0) AS jornadas
FROM areas a WHERE a.archivado_en IS NULL ORDER BY a.orden,a.nombre;
