-- Sorteo Studio v0.2.0 | MySQL 8.0.16+ / MariaDB 10.4+
-- HOSTING: crear la base y asignar el usuario desde cPanel antes de importar.
-- Seleccionar la base correspondiente en phpMyAdmin.
-- No incluye CREATE DATABASE, USE, GRANT ni DEFINER fijo.
-- Importar en una base vacia. No contiene DROP TABLE ni datos de prueba.
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS app_lock (
    id TINYINT UNSIGNED NOT NULL PRIMARY KEY,
    CONSTRAINT ck_lock_single CHECK (id = 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT IGNORE INTO app_lock (id) VALUES (1);

CREATE TABLE IF NOT EXISTS raffles (
    id CHAR(24) CHARACTER SET ascii COLLATE ascii_bin NOT NULL PRIMARY KEY,
    title VARCHAR(180) NOT NULL,
    description TEXT NOT NULL,
    type ENUM('producto','dinero') NOT NULL,
    total INT UNSIGNED NOT NULL,
    price_cents INT UNSIGNED NOT NULL,
    status ENUM('borrador','activo','finalizado') NOT NULL DEFAULT 'borrador',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    finalized_at DATETIME NULL,
    INDEX ix_raffle_status_date (status, created_at),
    CONSTRAINT ck_raffle_total CHECK (total BETWEEN 1 AND 1000000),
    CONSTRAINT ck_raffle_price CHECK (price_cents <= 99999999),
    CONSTRAINT ck_raffle_finalized CHECK (
       (status = 'finalizado' AND finalized_at IS NOT NULL) OR
       (status <> 'finalizado' AND finalized_at IS NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS raffle_photos (
    raffle_id CHAR(24) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    slot TINYINT UNSIGNED NOT NULL,
    filename VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    PRIMARY KEY (raffle_id, slot),
    UNIQUE KEY uq_photo_filename (filename),
    CONSTRAINT ck_photo_slot CHECK (slot BETWEEN 1 AND 3),
    CONSTRAINT fk_photo_raffle FOREIGN KEY (raffle_id) REFERENCES raffles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS participants (
    id CHAR(24) CHARACTER SET ascii COLLATE ascii_bin NOT NULL PRIMARY KEY,
    raffle_id CHAR(24) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    name VARCHAR(180) NOT NULL,
    email VARCHAR(254) NOT NULL DEFAULT '',
    phone VARCHAR(50) NOT NULL DEFAULT '',
    number INT UNSIGNED NOT NULL,
    payment ENUM('pendiente','pagado') NOT NULL DEFAULT 'pendiente',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uq_raffle_number (raffle_id, number),
    UNIQUE KEY uq_participant_raffle_number (raffle_id, number, id),
    INDEX ix_participant_payment (raffle_id, payment),
    CONSTRAINT ck_participant_number CHECK (number BETWEEN 1 AND 1000000),
    CONSTRAINT fk_participant_raffle FOREIGN KEY (raffle_id) REFERENCES raffles(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Reservada para la siguiente fase: ZIP original, sin PDF ni contrasena en claro.
-- La huella se calcula sobre los bytes del ZIP, no sobre el PDF.
CREATE TABLE IF NOT EXISTS raffle_evidence (
    raffle_id CHAR(24) CHARACTER SET ascii COLLATE ascii_bin NOT NULL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    storage_key VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    size_bytes BIGINT UNSIGNED NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at DATETIME NULL,
    UNIQUE KEY uq_evidence_storage (storage_key),
    CONSTRAINT ck_evidence_size CHECK (size_bytes > 0),
    CONSTRAINT ck_evidence_hash CHECK (CHAR_LENGTH(sha256) = 64 AND sha256 = LOWER(sha256)),
    CONSTRAINT fk_evidence_raffle FOREIGN KEY (raffle_id) REFERENCES raffles(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Reservada: no registrar ganadores antes de revelar el PDF.
-- Se admite resultado sin titular (numero no vendido); no se autoriza reclamo por ello.
CREATE TABLE IF NOT EXISTS winners (
    raffle_id CHAR(24) CHARACTER SET ascii COLLATE ascii_bin NOT NULL PRIMARY KEY,
    winning_number INT UNSIGNED NOT NULL,
    participant_id CHAR(24) CHARACTER SET ascii COLLATE ascii_bin NULL,
    claim_code_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
    claim_status ENUM('pendiente','reclamado') NOT NULL DEFAULT 'pendiente',
    revealed_at DATETIME NOT NULL,
    claimed_at DATETIME NULL,
    CONSTRAINT ck_winner_number CHECK (winning_number BETWEEN 1 AND 1000000),
    CONSTRAINT ck_winner_claim CHECK (
      (claim_status = 'pendiente' AND claimed_at IS NULL) OR
      (claim_status = 'reclamado' AND claimed_at IS NOT NULL AND participant_id IS NOT NULL)
    ),
    CONSTRAINT fk_winner_evidence FOREIGN KEY (raffle_id) REFERENCES raffle_evidence(raffle_id) ON DELETE RESTRICT,
    CONSTRAINT fk_winner_participant FOREIGN KEY (raffle_id, winning_number, participant_id)
      REFERENCES participants(raffle_id, number, id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Reservada: no se crea una cuenta ni una contrasena por defecto.
CREATE TABLE IF NOT EXISTS admins (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Bitacora interna, no es evidencia externa ni inmutable ante un DBA.
CREATE TABLE IF NOT EXISTS audit_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    admin_id BIGINT UNSIGNED NULL,
    entity_type ENUM('raffle','participant','evidence','winner','admin') NOT NULL,
    entity_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    action ENUM('create','update','delete') NOT NULL,
    details JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_audit_entity (entity_type, entity_id, created_at),
    CONSTRAINT fk_audit_admin FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Los ingresos se calculan a partir de participants.payment y raffles.price_cents.
-- Vista SQL opcional en ingresos_vista_opcional.sql.
