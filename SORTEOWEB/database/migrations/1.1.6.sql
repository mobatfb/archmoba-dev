-- SORTEOWEB 1.1.6: monedero y recargas. Ejecutar despues de 1.1.0.
-- Montos enteros en centavos de USD. No modifica boletos ni usuarios existentes.
CREATE TABLE IF NOT EXISTS wallet_recharges (
    id CHAR(24) CHARACTER SET ascii COLLATE ascii_bin NOT NULL PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    amount_cents INT UNSIGNED NOT NULL,
    provider VARCHAR(20) NOT NULL DEFAULT 'payphone',
    provider_tx_id BIGINT UNSIGNED NULL UNIQUE,
    payment_id VARCHAR(128) NULL,
    state ENUM('preparing','pending','review','approved','canceled','failed') NOT NULL DEFAULT 'preparing',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    confirmed_at DATETIME NULL,
    KEY ix_wallet_recharges_user(user_id,created_at),
    CONSTRAINT fk_wallet_recharges_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT ck_wallet_recharges_positive CHECK(amount_cents>0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS wallet_movements (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    direction ENUM('in','out') NOT NULL,
    amount_cents INT UNSIGNED NOT NULL,
    concept VARCHAR(180) NOT NULL,
    reference VARCHAR(80) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
    recharge_id CHAR(24) CHARACTER SET ascii COLLATE ascii_bin NULL UNIQUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_wallet_movements_user(user_id,id),
    CONSTRAINT fk_wallet_movements_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_wallet_movements_recharge FOREIGN KEY(recharge_id) REFERENCES wallet_recharges(id) ON DELETE RESTRICT,
    CONSTRAINT ck_wallet_movements_positive CHECK(amount_cents>0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
