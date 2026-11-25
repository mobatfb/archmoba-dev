-- SGA UNEDID: calificación cualitativa de comportamiento por matrícula y trimestre.
-- Ejecutar UNA VEZ en phpMyAdmin DESPUÉS de realizar un respaldo.
-- NO reemplaza usuarios, aulas, matrículas ni calificaciones existentes.
CREATE TABLE IF NOT EXISTS comportamiento_trimestre (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  matricula_id INT UNSIGNED NOT NULL,
  trimestre TINYINT UNSIGNED NOT NULL,
  literal VARCHAR(2) NOT NULL,
  registrado_por INT UNSIGNED NULL,
  actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_comportamiento_matricula_trimestre (matricula_id, trimestre),
  KEY idx_comportamiento_usuario (registrado_por),
  CONSTRAINT fk_comportamiento_matricula FOREIGN KEY (matricula_id) REFERENCES matriculas(id) ON DELETE CASCADE,
  CONSTRAINT fk_comportamiento_usuario FOREIGN KEY (registrado_por) REFERENCES usuarios(id) ON DELETE SET NULL,
  CONSTRAINT chk_comportamiento_trimestre CHECK (trimestre BETWEEN 1 AND 3),
  CONSTRAINT chk_comportamiento_literal CHECK (literal IN ('A+','A-','B+','B-','C+','C-','D+','D-','E+','E-','F+','F-'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
