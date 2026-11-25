-- SGA UNEDID: AREA / ASIGNATURA - MIGRACION SIN ELIMINAR DATOS
-- Compatible con MariaDB 10.6 (hosting phpMyAdmin).
-- Ejecutar UNA SOLA VEZ sobre la BD existente y despues de crear un respaldo.
-- Conservar los ID originales de asignaturas, ofertas, matriculas y calificaciones.
-- NO utilizar junto con el volcado completo.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `areas` (
  `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT,
  `codigo` varchar(30) NOT NULL,
  `nombre` varchar(150) NOT NULL,
  `orden` smallint(5) UNSIGNED NOT NULL DEFAULT 1,
  `activo` tinyint(1) NOT NULL DEFAULT 1,
  `creado_en` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_areas_codigo` (`codigo`),
  UNIQUE KEY `uq_areas_nombre` (`nombre`),
  KEY `idx_areas_orden` (`orden`,`nombre`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Áreas sugeridas en el registro de calificaciones proporcionado.
INSERT INTO `areas` (`codigo`,`nombre`,`orden`,`activo`) VALUES
('LYL', 'LENGUA Y LITERATURA', 1, 1),
('MAT', 'MATEMÁTICA', 2, 1),
('CCSS', 'CIENCIAS SOCIALES', 3, 1),
('CCNN', 'CIENCIAS NATURALES', 4, 1),
('ECA', 'ED. CULTURAL Y ARTÍSTICA', 5, 1),
('EDF', 'EDUCACIÓN FÍSICA', 6, 1),
('LEX', 'LENGUA EXTRANJERA', 7, 1),
('INF', 'INFORMÁTICA', 8, 1),
('CIV', 'CÍVICA Y ACOMPAÑAMIENTO INTEGRAL EN EL AULA', 9, 1)
ON DUPLICATE KEY UPDATE `codigo`=VALUES(`codigo`);

-- La columna se incorpora primero como NULL para asignar las materias antiguas.
ALTER TABLE `asignaturas`
  ADD COLUMN `area_id` int(10) UNSIGNED NULL AFTER `nombre`;

-- Asignaturas EXISTENTES en el volcado recibido (sin cambiarlas de ID).
-- Se usan codigos y nombres para tolerar tildes o pequenas variaciones.
UPDATE `asignaturas` SET `area_id`=(SELECT id FROM areas WHERE codigo='MAT')
  WHERE `area_id` IS NULL AND (`codigo`='MAT' OR `nombre` COLLATE utf8mb4_unicode_ci='Matematica');
UPDATE `asignaturas` SET `area_id`=(SELECT id FROM areas WHERE codigo='LYL')
  WHERE `area_id` IS NULL AND (`codigo`='LEN' OR `nombre` COLLATE utf8mb4_unicode_ci='Lengua y Literatura');
UPDATE `asignaturas` SET `area_id`=(SELECT id FROM areas WHERE codigo='CCNN')
  WHERE `area_id` IS NULL AND (`codigo`='CCNN' OR `nombre` COLLATE utf8mb4_unicode_ci='Ciencias Naturales');
UPDATE `asignaturas` SET `area_id`=(SELECT id FROM areas WHERE codigo='CCSS')
  WHERE `area_id` IS NULL AND (`codigo`='EESS' OR `nombre` COLLATE utf8mb4_unicode_ci='Estudios Sociales');

-- Comprobar primero esta consulta. En el respaldo entregado deben aparecer 0 pendientes:
SELECT `id`,`codigo`,`nombre` FROM `asignaturas` WHERE `area_id` IS NULL;
-- Si aparecieron asignaturas NO previstas, clasificalas antes de ejecutar lo siguiente.
-- Si no quedan asignaturas sin clasificar, se impone relacion obligatoria.
ALTER TABLE `asignaturas`
  MODIFY COLUMN `area_id` int(10) UNSIGNED NOT NULL,
  ADD KEY `idx_asignaturas_area` (`area_id`),
  ADD CONSTRAINT `fk_asignatura_area` FOREIGN KEY (`area_id`) REFERENCES `areas` (`id`)
    ON UPDATE CASCADE ON DELETE RESTRICT;

-- Comprobacion final:
SELECT s.id,s.codigo,s.nombre,ar.codigo AS area_codigo,ar.nombre AS area
FROM asignaturas s JOIN areas ar ON ar.id=s.area_id
ORDER BY ar.orden,s.nombre;
