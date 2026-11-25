-- SGA UNEDID | Evaluacion cualitativa por parametros | MariaDB 10.6+
-- RESPALDAR LA BASE DE DATOS ANTES DE EJECUTAR.
-- Instalar antes de subir los nuevos archivos PHP.
-- Por defecto ninguna asignatura cambia de modalidad.

ALTER TABLE `asignaturas`
  ADD COLUMN IF NOT EXISTS `evaluacion_cualitativa_parametros` TINYINT(1) NOT NULL DEFAULT 0
  COMMENT '1=evaluacion cualitativa directa por ejes y ambitos, sin promedios numericos';

-- Los parametros se configuran por oferta (asignatura + aula + periodo):
-- cambiar un aula o periodo NO altera automaticamente la configuracion historica.
CREATE TABLE IF NOT EXISTS `sga_parametros_cualitativos` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `oferta_id` INT UNSIGNED NOT NULL,
  `eje` VARCHAR(180) NOT NULL,
  `ambito` VARCHAR(220) NOT NULL,
  `orden` SMALLINT UNSIGNED NOT NULL DEFAULT 100,
  `activo` TINYINT(1) NOT NULL DEFAULT 1,
  `creado_en` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `ix_sga_parametros_oferta` (`oferta_id`,`activo`,`orden`),
  CONSTRAINT `fk_sga_param_oferta` FOREIGN KEY (`oferta_id`) REFERENCES `ofertas_academicas` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `sga_calificaciones_parametros` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `oferta_id` INT UNSIGNED NOT NULL,
  `matricula_id` INT UNSIGNED NOT NULL,
  `parametro_id` INT UNSIGNED NOT NULL,
  `trimestre` TINYINT UNSIGNED NOT NULL,
  `literal` VARCHAR(2) NOT NULL,
  `registrado_por` INT UNSIGNED NOT NULL,
  `creado_en` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `actualizado_en` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sga_calif_parametros` (`parametro_id`,`matricula_id`,`trimestre`),
  INDEX `ix_sga_calif_param_oferta` (`oferta_id`,`trimestre`),
  INDEX `ix_sga_calif_param_matricula` (`matricula_id`),
  CONSTRAINT `fk_sga_calif_param_oferta` FOREIGN KEY (`oferta_id`) REFERENCES `ofertas_academicas` (`id`),
  CONSTRAINT `fk_sga_calif_param_matricula` FOREIGN KEY (`matricula_id`) REFERENCES `matriculas` (`id`),
  CONSTRAINT `fk_sga_calif_param_parametro` FOREIGN KEY (`parametro_id`) REFERENCES `sga_parametros_cualitativos` (`id`),
  CONSTRAINT `fk_sga_calif_param_actor` FOREIGN KEY (`registrado_por`) REFERENCES `usuarios` (`id`),
  CONSTRAINT `ck_sga_calif_param_trimestre` CHECK (`trimestre` IN (1,2,3)),
  CONSTRAINT `ck_sga_calif_param_literal` CHECK (`literal` IN ('A+','A-','B+','B-','C+','C-','D+','D-','E+','E-'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- V2: el aula define la modalidad; aulas_periodo conserva su modalidad historica.
-- Ejecutar con el SGA en mantenimiento. No elimina notas ni ambitos.
ALTER TABLE aulas ADD COLUMN IF NOT EXISTS evaluacion_cualitativa_parametros TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE aulas_periodo ADD COLUMN IF NOT EXISTS evaluacion_cualitativa_parametros TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE ofertas_academicas
  ADD COLUMN IF NOT EXISTS evaluacion_aula TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS evaluacion_parametros_historica TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS aula_parametros_unica INT UNSIGNED GENERATED ALWAYS AS (CASE WHEN evaluacion_aula=1 THEN aula_periodo_id ELSE NULL END) PERSISTENT,
  ADD UNIQUE INDEX IF NOT EXISTS uq_sga_evaluacion_aula (aula_parametros_unica);

-- Registro interno necesario para reutilizar las ofertas, asistencia, listas y reportes.
-- Inactivo en los catalogos; nunca se selecciona como asignatura ordinaria.
INSERT INTO areas(codigo,nombre,orden,activo)
SELECT 'SGA_PARAM_AULA_INTERNO','Evaluacion integral de aula (interno)',9999,0
WHERE NOT EXISTS (SELECT 1 FROM areas WHERE codigo='SGA_PARAM_AULA_INTERNO');
INSERT INTO asignaturas(codigo,nombre,area_id,usa_literal_especial,solo_visor_comportamiento,activo)
SELECT 'SGA_PARAM_AULA_INTERNO','Evaluación cualitativa del aula',a.id,0,0,0
FROM areas a WHERE a.codigo='SGA_PARAM_AULA_INTERNO' AND a.archivado_en IS NULL
AND NOT EXISTS (SELECT 1 FROM asignaturas WHERE codigo='SGA_PARAM_AULA_INTERNO');

START TRANSACTION;
-- Solo se migra automaticamente un modelo que ya fue inicializado por el parche anterior.
-- Marcas de asignaturas sin modelo no activan aulas por si solas.
-- Los periodos cerrados conservan su estructura anterior, en solo lectura.
DROP TEMPORARY TABLE IF EXISTS tmp_sga_modelos_previos;
CREATE TEMPORARY TABLE tmp_sga_modelos_previos AS
SELECT o.id oferta_id,o.aula_periodo_id,o.activo,
       EXISTS(SELECT 1 FROM sga_calificaciones_parametros c WHERE c.oferta_id=o.id) tiene_notas
FROM ofertas_academicas o JOIN asignaturas s ON s.id=o.asignatura_id
JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id
JOIN periodos_academicos p ON p.id=ap.periodo_id
WHERE s.evaluacion_cualitativa_parametros=1 AND o.evaluacion_aula=0
AND EXISTS(SELECT 1 FROM sga_parametros_cualitativos q WHERE q.oferta_id=o.id);
UPDATE ofertas_academicas o JOIN asignaturas s ON s.id=o.asignatura_id
JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id JOIN periodos_academicos p ON p.id=ap.periodo_id
SET o.evaluacion_parametros_historica=1
WHERE s.evaluacion_cualitativa_parametros=1 AND (p.estado='cerrado' OR EXISTS(SELECT 1 FROM sga_parametros_cualitativos q WHERE q.oferta_id=o.id));
DROP TEMPORARY TABLE IF EXISTS tmp_sga_aulas_previas;
CREATE TEMPORARY TABLE tmp_sga_aulas_previas AS
SELECT aula_periodo_id, SUM(tiene_notas) fuentes_con_notas,
       CASE WHEN SUM(tiene_notas)=1 THEN MAX(CASE WHEN tiene_notas=1 THEN oferta_id END)
            WHEN SUM(tiene_notas)=0 AND COUNT(*)=1 THEN MIN(oferta_id)
            ELSE NULL END oferta_elegida
FROM tmp_sga_modelos_previos GROUP BY aula_periodo_id;
UPDATE aulas_periodo ap JOIN tmp_sga_aulas_previas t ON t.aula_periodo_id=ap.id
JOIN periodos_academicos p ON p.id=ap.periodo_id
SET ap.evaluacion_cualitativa_parametros=1 WHERE p.estado<>'cerrado';
UPDATE aulas a JOIN aulas_periodo ap ON ap.aula_id=a.id
JOIN tmp_sga_aulas_previas t ON t.aula_periodo_id=ap.id
JOIN periodos_academicos p ON p.id=ap.periodo_id
SET a.evaluacion_cualitativa_parametros=1 WHERE p.estado<>'cerrado';
UPDATE ofertas_academicas o JOIN tmp_sga_aulas_previas t ON t.oferta_elegida=o.id
JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id JOIN periodos_academicos p ON p.id=ap.periodo_id
LEFT JOIN ofertas_academicas x ON x.aula_periodo_id=o.aula_periodo_id AND x.evaluacion_aula=1
SET o.evaluacion_aula=1 WHERE p.estado<>'cerrado' AND x.id IS NULL;
-- Conservar selecciones y ofertas inactivas; no eliminar registros ordinarios.
UPDATE ofertas_academicas o JOIN tmp_sga_aulas_previas t ON t.aula_periodo_id=o.aula_periodo_id
JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id JOIN periodos_academicos p ON p.id=ap.periodo_id
SET o.activo=0 WHERE p.estado<>'cerrado' AND o.evaluacion_aula=0;
-- La marca antigua ya no controla la evaluacion; se conserva la columna por compatibilidad SQL.
UPDATE asignaturas SET evaluacion_cualitativa_parametros=0 WHERE evaluacion_cualitativa_parametros<>0;
COMMIT;
-- Revisar aulas con modelos previos multiples; el administrador puede elegir el principal en el aula.
SELECT ap.id aula_periodo_id,a.nombre,a.paralelo,t.fuentes_con_notas
FROM tmp_sga_aulas_previas t JOIN aulas_periodo ap ON ap.id=t.aula_periodo_id JOIN aulas a ON a.id=ap.aula_id
WHERE t.oferta_elegida IS NULL AND ap.evaluacion_cualitativa_parametros=1;
DROP TEMPORARY TABLE IF EXISTS tmp_sga_aulas_previas;
DROP TEMPORARY TABLE IF EXISTS tmp_sga_modelos_previos;
