-- SGA UNEDID | Flotantes del aula: asignaturas seleccionadas y docentes por asignatura
-- Primero hacer copia de seguridad de la base de datos. MariaDB/MySQL con InnoDB.
-- Esta tabla conserva la seleccion incluso cuando no se ha asignado un docente.
-- No altera ni elimina ofertas academicas, matriculas, calificaciones o asistencias.
CREATE TABLE IF NOT EXISTS aula_asignaturas_seleccionadas (
    aula_periodo_id INT UNSIGNED NOT NULL,
    asignatura_id INT UNSIGNED NOT NULL,
    seleccionada TINYINT(1) NOT NULL DEFAULT 1,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (aula_periodo_id, asignatura_id),
    KEY idx_sga_aas_asignatura (asignatura_id),
    KEY idx_sga_aas_estado (aula_periodo_id, seleccionada)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Preselecciona las asignaturas que ya tienen una oferta activa.
-- No modifica en absoluto las ofertas existentes ni su historial.
INSERT IGNORE INTO aula_asignaturas_seleccionadas (aula_periodo_id, asignatura_id, seleccionada)
SELECT DISTINCT o.aula_periodo_id,o.asignatura_id,1
FROM ofertas_academicas o
WHERE o.activo=1;
