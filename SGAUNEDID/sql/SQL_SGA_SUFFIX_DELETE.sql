-- SGA UNEDID - SUFIJO [DELETE] SIN ELIMINAR REGISTROS
-- APLICAR DESPUES de SQL_SGA_BORRADO_LOGICO_CATALOGOS.sql del parche anterior.
-- Ejecucion en phpMyAdmin. Requiere copia de seguridad.
-- Amplia los campos para conservar INTEGROS los valores originales
-- y poder anadir [DELETE] sin truncamiento (incluidas tildes / Unicode).
-- Mantiene claves unicas y IDs; no elimina ningun dato.

ALTER TABLE `areas`
  MODIFY COLUMN `codigo` VARCHAR(64) NOT NULL,
  MODIFY COLUMN `nombre` VARCHAR(200) NOT NULL,
  ADD COLUMN IF NOT EXISTS `codigo_original_borrado` VARCHAR(30) NULL DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS `nombre_original_borrado` VARCHAR(150) NULL DEFAULT NULL;

ALTER TABLE `asignaturas`
  MODIFY COLUMN `codigo` VARCHAR(64) NULL DEFAULT NULL,
  MODIFY COLUMN `nombre` VARCHAR(200) NOT NULL,
  ADD COLUMN IF NOT EXISTS `codigo_original_borrado` VARCHAR(30) NULL DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS `nombre_original_borrado` VARCHAR(150) NULL DEFAULT NULL;

-- No cambia automaticamente los nombres de registros ya ocultos.
-- Para eso, abrir /migrar_archivados_delete.php como Administrador
-- despues de instalar el archivo PHP y pulsar el boton una sola vez.
-- Esta separacion evita perder nombres por conflictos UNIQUE.

SELECT 'areas' tabla, COUNT(*) borrados_sin_sufijo
 FROM `areas` WHERE `archivado_en` IS NOT NULL AND `nombre_original_borrado` IS NULL
UNION ALL
SELECT 'asignaturas', COUNT(*)
 FROM `asignaturas` WHERE `archivado_en` IS NOT NULL AND `nombre_original_borrado` IS NULL;
