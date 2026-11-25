-- Parche 1.5. Ejecutar una unica vez en la BD del SGA, antes de usar el recuperador.
-- No modifica tablas, cuentas, contrasenas, roles ni matriculas existentes.
CREATE TABLE IF NOT EXISTS sga_recuperacion_claves (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  usuario_id INT NOT NULL,
  token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  vence_en DATETIME NOT NULL,
  usado_en DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_sga_recuperacion_token (token_hash),
  KEY idx_sga_recuperacion_usuario (usuario_id, usado_en),
  KEY idx_sga_recuperacion_vence (vence_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sga_recuperacion_solicitudes (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  ip_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  correo_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_sga_reset_ip_fecha (ip_hash, creado_en),
  KEY idx_sga_reset_correo_fecha (correo_hash, creado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
