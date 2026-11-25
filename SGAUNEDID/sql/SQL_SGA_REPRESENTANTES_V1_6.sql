-- SGA UNEDID V1.6 | Representantes y notificaciones
-- Ejecutar en la misma BD del SGA (MariaDB 10.6+). Respaldar antes.
-- No borra ni actualiza cuentas, matriculas, calificaciones o roles existentes.

INSERT INTO roles (codigo, nombre)
SELECT 'representante', 'Representante'
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE codigo = 'representante');

-- Relacion permanente muchos a muchos. No depende de un periodo academico.
CREATE TABLE IF NOT EXISTS sga_representantes_estudiantes (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  representante_id INT UNSIGNED NOT NULL,
  estudiante_id INT UNSIGNED NOT NULL,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  creado_por INT UNSIGNED NULL,
  actualizado_por INT UNSIGNED NULL,
  creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_sga_rep_hijo (representante_id, estudiante_id),
  KEY idx_sga_rep_estudiante (estudiante_id, activo),
  KEY idx_sga_rep_representante (representante_id, activo),
  CONSTRAINT fk_sga_rep_adulto FOREIGN KEY (representante_id) REFERENCES usuarios(id),
  CONSTRAINT fk_sga_rep_menor FOREIGN KEY (estudiante_id) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Cada novedad pertenece a un estudiante y deja trazabilidad de su autor.
CREATE TABLE IF NOT EXISTS sga_representantes_novedades (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  estudiante_id INT UNSIGNED NOT NULL,
  periodo_id INT UNSIGNED NOT NULL,
  creada_por INT UNSIGNED NOT NULL,
  tipo VARCHAR(30) NOT NULL,
  asunto VARCHAR(180) NOT NULL,
  detalle TEXT NOT NULL,
  evento_clave VARCHAR(190) NULL,
  creada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_sga_rep_evento (evento_clave),
  KEY idx_sga_rep_novedad_estudiante (estudiante_id, creada_en),
  KEY idx_sga_rep_novedad_periodo (periodo_id, creada_en),
  CONSTRAINT fk_sga_rep_novedad_hijo FOREIGN KEY (estudiante_id) REFERENCES usuarios(id),
  CONSTRAINT fk_sga_rep_novedad_periodo FOREIGN KEY (periodo_id) REFERENCES periodos_academicos(id),
  CONSTRAINT fk_sga_rep_novedad_autor FOREIGN KEY (creada_por) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Un correo independiente por representante. Permite reintentos y auditoria de envio.
CREATE TABLE IF NOT EXISTS sga_representantes_envios (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  novedad_id BIGINT UNSIGNED NOT NULL,
  representante_id INT UNSIGNED NOT NULL,
  correo_destino VARCHAR(254) NULL,
  estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
  intentos TINYINT UNSIGNED NOT NULL DEFAULT 0,
  ultimo_error VARCHAR(160) NULL,
  enviado_en DATETIME NULL,
  actualizado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_sga_rep_envio_destino (novedad_id, representante_id),
  KEY idx_sga_rep_envio_cola (estado, intentos, actualizado_en),
  CONSTRAINT fk_sga_rep_envio_novedad FOREIGN KEY (novedad_id) REFERENCES sga_representantes_novedades(id),
  CONSTRAINT fk_sga_rep_envio_adulto FOREIGN KEY (representante_id) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SELECT 'Rol y tablas de representantes verificados. No se modificaron datos previos.' AS resultado;
