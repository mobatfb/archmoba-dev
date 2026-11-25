-- SGA UNEDID | Modulo de Notificaciones Institucionales por Jornada
-- Ejecutar UNA VEZ en phpMyAdmin, en la misma BD del SGA, ANTES de abrir el modulo.
-- MariaDB 10.6+ | Compatible PHP 8.1+ | No modifica calificaciones ni usuarios.

CREATE TABLE IF NOT EXISTS sga_notificaciones_jornadas (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  periodo_id INT UNSIGNED NOT NULL,
  remitente_id INT UNSIGNED NOT NULL,
  jornada_id INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '0 = Todas las jornadas autorizadas al remitente',
  asunto VARCHAR(150) NOT NULL,
  mensaje TEXT NOT NULL,
  creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_sga_notif_remitente (remitente_id, creado_en),
  KEY idx_sga_notif_periodo (periodo_id, creado_en),
  CONSTRAINT fk_sga_notif_periodo FOREIGN KEY (periodo_id) REFERENCES periodos_academicos(id),
  CONSTRAINT fk_sga_notif_remitente FOREIGN KEY (remitente_id) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sga_notificaciones_jornadas_envios (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  notificacion_id BIGINT UNSIGNED NOT NULL,
  destinatario_id INT UNSIGNED NOT NULL,
  correo_destino VARCHAR(254) NOT NULL,
  estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
  intentos TINYINT UNSIGNED NOT NULL DEFAULT 0,
  ultimo_error VARCHAR(160) NULL,
  enviado_en DATETIME NULL,
  actualizado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_sga_notif_destino (notificacion_id, destinatario_id),
  KEY idx_sga_notif_cola (estado, intentos, actualizado_en),
  CONSTRAINT fk_sga_notif_envio FOREIGN KEY (notificacion_id) REFERENCES sga_notificaciones_jornadas(id),
  CONSTRAINT fk_sga_notif_destinatario FOREIGN KEY (destinatario_id) REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SELECT 'Modulo de notificaciones por jornada instalado correctamente.' AS resultado;
