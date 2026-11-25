-- SORTEOWEB 1.0.1: actualizar la base existente (MariaDB 11.4).
-- Selecciona la base de sorteos en phpMyAdmin. Realiza respaldo antes.
-- No elimina tablas, registros, usuarios ni contraseñas.
SET NAMES utf8mb4;
ALTER TABLE admins ADD COLUMN IF NOT EXISTS must_change_password TINYINT(1) NOT NULL DEFAULT 1;
ALTER TABLE raffle_photos ADD COLUMN IF NOT EXISTS mime VARCHAR(32) NULL, ADD COLUMN IF NOT EXISTS content MEDIUMBLOB NULL;
CREATE TABLE IF NOT EXISTS login_limits (
 bucket CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 window_start INT UNSIGNED NOT NULL,
 attempts INT UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
