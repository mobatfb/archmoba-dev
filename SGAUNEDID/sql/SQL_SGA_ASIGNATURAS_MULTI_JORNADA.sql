-- Ejecutar una sola vez (MariaDB 10.6+). Crear copia de seguridad previamente.
-- Las asignaturas existentes heredan todas las jornadas de su area actual.
ALTER TABLE `asignaturas` ADD COLUMN IF NOT EXISTS `jornadas_ids` VARCHAR(512) NULL DEFAULT NULL AFTER `area_id`;
UPDATE `asignaturas` s
INNER JOIN `areas` a ON a.id=s.area_id
SET s.jornadas_ids=a.jornadas_ids
WHERE s.jornadas_ids IS NULL OR TRIM(s.jornadas_ids)='';
