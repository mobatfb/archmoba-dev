-- SGA UNEDID - MIGRACION PARA BORRADO LOGICO (SIN ELIMINAR DATOS)
-- EJECUTAR UNA SOLA VEZ EN PHPMYADMIN, ANTES DE SUBIR LOS PHP DEL PARCHE.
-- Requiere MariaDB 10.6+ (ADD COLUMN IF NOT EXISTS).
-- Conserva areas, asignaturas, ofertas, notas, asistencias e historiales.
-- Copia de seguridad obligatoria antes de ejecutar.

ALTER TABLE `areas`
  ADD COLUMN IF NOT EXISTS `archivado_en` DATETIME NULL DEFAULT NULL;

ALTER TABLE `asignaturas`
  ADD COLUMN IF NOT EXISTS `archivado_en` DATETIME NULL DEFAULT NULL;

-- Verificacion: estos conteos inicialmente deben ser 0.
SELECT 'areas_ocultas' AS tabla, COUNT(*) AS registros FROM `areas` WHERE `archivado_en` IS NOT NULL
UNION ALL
SELECT 'asignaturas_ocultas', COUNT(*) FROM `asignaturas` WHERE `archivado_en` IS NOT NULL;
