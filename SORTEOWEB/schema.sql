-- SORTEOWEB v1.0.0. Seleccionar la base de datos en phpMyAdmin antes de importar.
-- No elimina tablas previas. MySQL 8.0.16+ / MariaDB 10.4+.
SET NAMES utf8mb4;
CREATE TABLE IF NOT EXISTS sw_admins (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 username VARCHAR(80) NOT NULL UNIQUE,
 password_hash VARCHAR(255) NOT NULL,
 must_change_password TINYINT(1) NOT NULL DEFAULT 1,
 active TINYINT(1) NOT NULL DEFAULT 1,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS sw_raffles (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 title VARCHAR(180) NOT NULL,
 description TEXT NOT NULL,
 type ENUM('producto','dinero') NOT NULL,
 ticket_count INT UNSIGNED NOT NULL,
 ticket_price_cents INT UNSIGNED NOT NULL,
 status ENUM('borrador','activo','finalizado') NOT NULL DEFAULT 'borrador',
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 closed_at DATETIME NULL,
 INDEX idx_status(status,created_at),
 CHECK(ticket_count BETWEEN 1 AND 1000000),
 CHECK(ticket_price_cents BETWEEN 1 AND 100000000)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS sw_photos (
 raffle_id BIGINT UNSIGNED NOT NULL,
 slot TINYINT UNSIGNED NOT NULL,
 mime VARCHAR(32) NOT NULL,
 content MEDIUMBLOB NOT NULL,
 PRIMARY KEY(raffle_id,slot),
 CONSTRAINT fk_sw_photos_raffle FOREIGN KEY(raffle_id) REFERENCES sw_raffles(id) ON DELETE CASCADE,
 CHECK(slot BETWEEN 1 AND 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS sw_participants (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 raffle_id BIGINT UNSIGNED NOT NULL,
 ticket_number INT UNSIGNED NOT NULL,
 name VARCHAR(180) NOT NULL,
 email VARCHAR(254) NOT NULL DEFAULT '',
 phone VARCHAR(40) NOT NULL DEFAULT '',
 payment_status ENUM('pendiente','pagado') NOT NULL DEFAULT 'pendiente',
 price_cents INT UNSIGNED NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 UNIQUE KEY uq_sw_ticket(raffle_id,ticket_number),
 INDEX idx_sw_payment(raffle_id,payment_status),
 CONSTRAINT fk_sw_participants_raffle FOREIGN KEY(raffle_id) REFERENCES sw_raffles(id) ON DELETE RESTRICT,
 CHECK(ticket_number>=1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS sw_audit (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 admin_id BIGINT UNSIGNED NOT NULL,
 action VARCHAR(60) NOT NULL,
 raffle_id BIGINT UNSIGNED NULL,
 detail VARCHAR(250) NOT NULL DEFAULT '',
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_sw_audit_raffle(raffle_id,created_at),
 CONSTRAINT fk_sw_audit_admin FOREIGN KEY(admin_id) REFERENCES sw_admins(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS sw_login_limits (
 bucket CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 window_start INT UNSIGNED NOT NULL,
 attempts INT UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
-- Estructura reservada para futura publicacion del ZIP/PDF. No almacena contrasenas.
CREATE TABLE IF NOT EXISTS sw_evidence (
 raffle_id BIGINT UNSIGNED PRIMARY KEY,
 archive_name VARCHAR(255) NOT NULL,
 archive_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 archive_size BIGINT UNSIGNED NOT NULL,
 published_at DATETIME NULL,
 CONSTRAINT fk_sw_evidence_raffle FOREIGN KEY(raffle_id) REFERENCES sw_raffles(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS sw_winners (
 raffle_id BIGINT UNSIGNED PRIMARY KEY,
 ticket_number INT UNSIGNED NOT NULL,
 published_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 claim_status ENUM('pendiente','entregado') NOT NULL DEFAULT 'pendiente',
 CONSTRAINT fk_sw_winners_ticket FOREIGN KEY(raffle_id,ticket_number) REFERENCES sw_participants(raffle_id,ticket_number) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
