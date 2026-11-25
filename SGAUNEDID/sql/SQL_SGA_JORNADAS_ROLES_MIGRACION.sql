-- SGA UNEDID | Migracion sin perdida de datos
-- Base objetivo: MariaDB 10.6 (exportacion del 12/11/2026).
-- IMPORTANTE: haga respaldo primero. NO elimine tablas ni cambie los IDs de aulas o usuarios.
-- La migracion deja la jornada de las aulas existentes como NULL (pendiente de asignacion).
-- Los roles docente/estudiante se actualizan UNICAMENTE para el periodo activo.

CREATE TABLE IF NOT EXISTS jornadas (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  codigo VARCHAR(30) NOT NULL,
  nombre VARCHAR(100) NOT NULL,
  orden SMALLINT UNSIGNED NOT NULL DEFAULT 1,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_jornadas_codigo (codigo),
  UNIQUE KEY uq_jornadas_nombre (nombre),
  KEY idx_jornadas_orden (orden, nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO jornadas (codigo, nombre, orden, activo)
SELECT 'MAT', 'MATUTINA', 1, 1 WHERE NOT EXISTS (SELECT 1 FROM jornadas WHERE codigo='MAT');
INSERT INTO jornadas (codigo, nombre, orden, activo)
SELECT 'VES', 'VESPERTINA', 2, 1 WHERE NOT EXISTS (SELECT 1 FROM jornadas WHERE codigo='VES');
INSERT INTO jornadas (codigo, nombre, orden, activo)
SELECT 'NOC', 'NOCTURNA', 3, 1 WHERE NOT EXISTS (SELECT 1 FROM jornadas WHERE codigo='NOC');

ALTER TABLE aulas ADD COLUMN IF NOT EXISTS jornada_id INT UNSIGNED NULL AFTER paralelo;
ALTER TABLE aulas ADD INDEX IF NOT EXISTS idx_aulas_jornada (jornada_id);
-- Agregar la FK solo si no existe, para tolerar una segunda ejecucion.
SET @fk_jornada = (SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME='aulas' AND CONSTRAINT_NAME='fk_aulas_jornada');
SET @sql_fk_jornada = IF(@fk_jornada=0,
    'ALTER TABLE aulas ADD CONSTRAINT fk_aulas_jornada FOREIGN KEY (jornada_id) REFERENCES jornadas (id)',
    'SELECT 1');
PREPARE stmt_jornada FROM @sql_fk_jornada;
EXECUTE stmt_jornada;
DEALLOCATE PREPARE stmt_jornada;

-- Se conserva el codigo interno superadmin utilizado por la autenticacion.
UPDATE roles SET nombre='Administrador' WHERE codigo='superadmin';
INSERT INTO roles (codigo,nombre)
SELECT 'subadmin','Subadministrador'
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE codigo='subadmin');

-- Identificacion exacta de Nathaly en la exportacion mas reciente.
-- Si la cuenta no coincide, NO se efectua la reasignacion masiva; revisar el SELECT final.
SET @nathaly_id = (
  SELECT id FROM usuarios WHERE id=345 AND UPPER(nombres) LIKE 'NATHALY%'
    AND UPPER(apellidos) LIKE 'MARTINEZ%' LIMIT 1
);
SET @periodo_id = (SELECT id FROM periodos_academicos WHERE estado='activo' ORDER BY id DESC LIMIT 1);
SET @rol_docente_id = (SELECT id FROM roles WHERE codigo='docente' LIMIT 1);
SET @rol_estudiante_id = (SELECT id FROM roles WHERE codigo='estudiante' LIMIT 1);

-- Conserva superadministradores y subadministradores, y el rol docente de Nathaly.
-- Preserva todos los roles de periodos anteriores.
START TRANSACTION;
DELETE ur FROM usuario_roles ur
INNER JOIN roles r ON r.id=ur.rol_id
LEFT JOIN usuario_roles protegido ON protegido.usuario_id=ur.usuario_id
  AND protegido.periodo_id IS NULL
  AND protegido.rol_id IN (SELECT id FROM roles WHERE codigo IN ('superadmin','subadmin'))
WHERE ur.periodo_id=@periodo_id
  AND r.codigo IN ('docente','estudiante')
  AND @nathaly_id IS NOT NULL AND @periodo_id IS NOT NULL
  AND ur.usuario_id<>@nathaly_id AND protegido.id IS NULL;

INSERT INTO usuario_roles (usuario_id,rol_id,periodo_id)
SELECT u.id,@rol_estudiante_id,@periodo_id
FROM usuarios u
WHERE @periodo_id IS NOT NULL AND @nathaly_id IS NOT NULL
  AND u.id<>@nathaly_id
  AND NOT EXISTS (
    SELECT 1 FROM usuario_roles ur
    JOIN roles r ON r.id=ur.rol_id
    WHERE ur.usuario_id=u.id AND r.codigo IN ('superadmin','subadmin')
  )
  AND NOT EXISTS (
    SELECT 1 FROM usuario_roles ur
    WHERE ur.usuario_id=u.id AND ur.rol_id=@rol_estudiante_id AND ur.periodo_id=@periodo_id
  );

DELETE ur FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id
WHERE ur.usuario_id=@nathaly_id AND ur.periodo_id=@periodo_id
  AND r.codigo='estudiante' AND @nathaly_id IS NOT NULL;
INSERT INTO usuario_roles (usuario_id,rol_id,periodo_id)
SELECT @nathaly_id,@rol_docente_id,@periodo_id
WHERE @periodo_id IS NOT NULL AND @nathaly_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM usuario_roles
    WHERE usuario_id=@nathaly_id AND rol_id=@rol_docente_id AND periodo_id=@periodo_id);
COMMIT;

-- Control posterior: Nathaly, periodo y total de personas por rol.
SELECT @nathaly_id AS nathaly_id_verificado, @periodo_id AS periodo_activo,
       IF(@nathaly_id IS NULL OR @periodo_id IS NULL,
          'ATENCION: no se aplico la asignacion masiva; verificar usuario y periodo',
          'Migracion de roles ejecutada') AS resultado;
SELECT r.nombre AS rol, COUNT(DISTINCT ur.usuario_id) AS usuarios
FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id
WHERE ur.periodo_id=@periodo_id OR (ur.periodo_id IS NULL AND r.codigo IN ('superadmin','subadmin'))
GROUP BY r.id,r.nombre ORDER BY r.id;
