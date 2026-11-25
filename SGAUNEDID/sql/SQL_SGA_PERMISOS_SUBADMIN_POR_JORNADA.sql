-- SGA UNEDID | Restricciones por jornada y periodo | MariaDB 10.6+
-- Antes de importar: realice una copia de seguridad de la base de datos.
-- Requisito: aplicar primero SQL_SGA_JORNADAS_ROLES_MIGRACION.sql.
-- Esta migracion NO borra ni reasigna usuarios, aulas, notas o matriculas.
-- Un subadministrador queda SIN acceso a un periodo hasta recibir jornadas explicitas en Roles.
-- Las jornadas MATUTINA y VESPERTINA se ofrecen como ejemplo en la interfaz,
-- pero no se asignan automaticamente a nadie.

CREATE TABLE IF NOT EXISTS subadministrador_jornadas (
    usuario_id INT UNSIGNED NOT NULL,
    periodo_id INT UNSIGNED NOT NULL,
    jornada_id INT UNSIGNED NOT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (usuario_id, periodo_id, jornada_id),
    KEY idx_saj_periodo_jornada (periodo_id, jornada_id),
    KEY idx_saj_jornada (jornada_id),
    CONSTRAINT fk_saj_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_saj_periodo FOREIGN KEY (periodo_id) REFERENCES periodos_academicos(id) ON DELETE CASCADE,
    CONSTRAINT fk_saj_jornada FOREIGN KEY (jornada_id) REFERENCES jornadas(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Registros provisionales de usuarios creados/importados para una jornada
-- (antes de su primera matricula o asignacion como docente).
CREATE TABLE IF NOT EXISTS usuarios_jornadas_gestion (
    usuario_id INT UNSIGNED NOT NULL,
    periodo_id INT UNSIGNED NOT NULL,
    jornada_id INT UNSIGNED NOT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (usuario_id, periodo_id, jornada_id),
    KEY idx_ujg_periodo_jornada (periodo_id, jornada_id),
    KEY idx_ujg_jornada (jornada_id),
    CONSTRAINT fk_ujg_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_ujg_periodo FOREIGN KEY (periodo_id) REFERENCES periodos_academicos(id) ON DELETE CASCADE,
    CONSTRAINT fk_ujg_jornada FOREIGN KEY (jornada_id) REFERENCES jornadas(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Comprobacion de permisos existentes: cero filas es normal hasta que el
-- superadministrador configure las jornadas desde Roles de usuarios.
SELECT sj.usuario_id, u.apellidos, u.nombres, p.nombre AS periodo, j.nombre AS jornada
FROM subadministrador_jornadas sj
JOIN usuarios u ON u.id=sj.usuario_id
JOIN periodos_academicos p ON p.id=sj.periodo_id
JOIN jornadas j ON j.id=sj.jornada_id
ORDER BY u.apellidos, u.nombres, p.anio_inicio, j.orden;
