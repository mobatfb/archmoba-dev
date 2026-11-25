-- SGA UNEDID - comportamiento CUALITATIVO por TRES TRIMESTRES.
-- Ejecutar una vez en phpMyAdmin, despues de respaldar la base de datos.
-- Es idempotente. No borra ni transforma calificaciones previas.
-- Si existe calificaciones_comportamiento_semestre, se CONSERVA sin migrarla:
-- los datos de semestres no representan automaticamente trimestres.
CREATE TABLE IF NOT EXISTS calificaciones_comportamiento_trimestre (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    oferta_id INT UNSIGNED NOT NULL,
    matricula_id INT UNSIGNED NOT NULL,
    trimestre TINYINT UNSIGNED NOT NULL,
    literal VARCHAR(2) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
    registrado_por INT UNSIGNED NOT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_comp_oferta_matricula_trim (oferta_id, matricula_id, trimestre),
    KEY idx_comp_trim_matricula (matricula_id),
    KEY idx_comp_trim_actor (registrado_por),
    CONSTRAINT fk_comp_trim_oferta FOREIGN KEY (oferta_id)
        REFERENCES ofertas_academicas(id) ON DELETE CASCADE,
    CONSTRAINT fk_comp_trim_matricula FOREIGN KEY (matricula_id)
        REFERENCES matriculas(id) ON DELETE CASCADE,
    CONSTRAINT fk_comp_trim_actor FOREIGN KEY (registrado_por)
        REFERENCES usuarios(id),
    CONSTRAINT chk_comp_trim_periodo CHECK (trimestre IN (1, 2, 3)),
    CONSTRAINT chk_comp_trim_literal CHECK (
        literal IN ('A+','A-','B+','B-','C+','C-','D+','D-','E+','E-','F+','F-')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
