-- SORTEOWEB 1.2.0 | MariaDB 11.4 | Run after 1.1.6. Back up first.
-- Existing active/finalized raffles remain legacy (draw_version=0).
ALTER TABLE raffles ADD COLUMN IF NOT EXISTS participation_mode ENUM('exclusivo','compartido') NOT NULL DEFAULT 'exclusivo', ADD COLUMN IF NOT EXISTS prize_cents BIGINT UNSIGNED NULL, ADD COLUMN IF NOT EXISTS closes_at BIGINT UNSIGNED NULL, ADD COLUMN IF NOT EXISTS close_mode ENUM('fecha','capacidad') NULL, ADD COLUMN IF NOT EXISTS participation_limit INT UNSIGNED NULL, ADD COLUMN IF NOT EXISTS draw_version TINYINT UNSIGNED NOT NULL DEFAULT 0, ADD COLUMN IF NOT EXISTS draw_outcome ENUM('premiado','devolucion_pendiente') NULL;
ALTER TABLE participants ADD COLUMN IF NOT EXISTS participation_mode ENUM('exclusivo','compartido') NOT NULL DEFAULT 'exclusivo', ADD COLUMN IF NOT EXISTS exclusive_number INT UNSIGNED GENERATED ALWAYS AS (CASE WHEN participation_mode='exclusivo' THEN number ELSE NULL END) PERSISTENT;
-- Add replacement constraints BEFORE removing the old exclusive-only index.
ALTER TABLE participants ADD UNIQUE INDEX IF NOT EXISTS uq_exclusive_number (raffle_id,exclusive_number), ADD UNIQUE INDEX IF NOT EXISTS uq_user_raffle_number (raffle_id,number,user_id);
ALTER TABLE participants DROP INDEX IF EXISTS uq_raffle_number;
ALTER TABLE raffle_evidence ADD COLUMN IF NOT EXISTS archive MEDIUMBLOB NULL, ADD COLUMN IF NOT EXISTS sealed_result VARBINARY(2048) NULL, ADD COLUMN IF NOT EXISTS revealed_number INT UNSIGNED NULL, ADD COLUMN IF NOT EXISTS revealed_password VARCHAR(96) CHARACTER SET ascii COLLATE ascii_bin NULL;
CREATE TABLE IF NOT EXISTS prize_awards (
 raffle_id CHAR(24) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 participant_id CHAR(24) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 winning_number INT UNSIGNED NOT NULL,
 prize_type ENUM('producto','dinero') NOT NULL,
 amount_cents BIGINT UNSIGNED NULL,
 status ENUM('pendiente','entregado') NOT NULL DEFAULT 'pendiente',
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(raffle_id,participant_id),
 CONSTRAINT fk_award_ticket FOREIGN KEY(raffle_id,winning_number,participant_id) REFERENCES participants(raffle_id,number,id),
 CONSTRAINT fk_award_result FOREIGN KEY(raffle_id) REFERENCES winners(raffle_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS raffle_refund_reviews (
 raffle_id CHAR(24) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 participant_id CHAR(24) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 amount_cents BIGINT UNSIGNED NOT NULL,
 reason VARCHAR(64) NOT NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(raffle_id,participant_id),
 CONSTRAINT fk_refund_raffle FOREIGN KEY(raffle_id) REFERENCES raffles(id),
 CONSTRAINT fk_refund_ticket FOREIGN KEY(participant_id) REFERENCES participants(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
