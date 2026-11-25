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
