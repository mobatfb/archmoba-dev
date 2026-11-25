-- SGA UNEDID - ORDEN CONSECUTIVO DE AREAS ACADEMICAS
-- EJECUTAR UNA SOLA VEZ sobre la base existente (tras hacer respaldo).
-- Cambia solamente areas.orden; conserva los ID, nombres, codigos y vinculaciones.
-- Compatible con MariaDB 10.6.
-- Se conserva el orden visual actual; no se ordena alfabeticamente salvo empates.

START TRANSACTION;

CREATE TEMPORARY TABLE `_sga_orden_consecutivo_areas` AS
SELECT `id`, ROW_NUMBER() OVER (ORDER BY `orden`, `nombre`, `id`) AS `orden_nuevo`
FROM `areas`;

UPDATE `areas` AS a
INNER JOIN `_sga_orden_consecutivo_areas` AS o ON o.`id` = a.`id`
SET a.`orden` = o.`orden_nuevo`;

DROP TEMPORARY TABLE `_sga_orden_consecutivo_areas`;
COMMIT;

-- Verificacion: 1, 2, 3, 4, 5, ...
SELECT `orden`, `codigo`, `nombre` FROM `areas` ORDER BY `orden`, `id`;
