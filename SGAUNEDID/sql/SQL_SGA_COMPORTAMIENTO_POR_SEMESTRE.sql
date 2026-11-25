-- SGA UNEDID - evaluacion cualitativa de comportamiento por semestre.
-- Ejecutar UNA SOLA VEZ en phpMyAdmin (tambien es seguro volver a ejecutar).
-- No altera ni convierte notas numericas historicas ni valoraciones antiguas.
CREATE TABLE IF NOT EXISTS calificaciones_comportamiento_semestre (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    oferta_id INT UNSIGNED NOT NULL,
    matricula_id INT UNSIGNED NOT NULL,
    semestre TINYINT UNSIGNED NOT NULL,
    literal VARCHAR(2) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
    registrado_por INT UNSIGNED NOT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_comportamiento_oferta_matricula_semestre (oferta_id, matricula_id, semestre),
    KEY idx_comportamiento_matricula (matricula_id),
    KEY idx_comportamiento_actor (registrado_por),
    CONSTRAINT fk_comportamiento_semestre_oferta FOREIGN KEY (oferta_id)
        REFERENCES ofertas_academicas(id) ON DELETE CASCADE,
    CONSTRAINT fk_comportamiento_semestre_matricula FOREIGN KEY (matricula_id)
        REFERENCES matriculas(id) ON DELETE CASCADE,
    CONSTRAINT fk_comportamiento_semestre_actor FOREIGN KEY (registrado_por)
        REFERENCES usuarios(id),
    CONSTRAINT chk_comportamiento_semestre_num CHECK (semestre IN (1, 2)),
    CONSTRAINT chk_comportamiento_semestre_literal CHECK (
        literal IN ('A+','A-','B+','B-','C+','C-','D+','D-','E+','E-','F+','F-')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
