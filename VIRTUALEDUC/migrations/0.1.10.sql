-- VIRTUALEDUC 0.1.10 - Configuracion institucional; conserva los datos existentes.
CREATE TABLE IF NOT EXISTS ve_institution_settings (
    id TINYINT UNSIGNED NOT NULL PRIMARY KEY,
    institution_name VARCHAR(180) NOT NULL DEFAULT 'VIRTUALEDUC',
    institution_subtitle VARCHAR(180) NOT NULL DEFAULT 'Plataforma académica institucional',
    institutional_phone VARCHAR(50) NOT NULL DEFAULT '',
    institutional_email VARCHAR(190) NOT NULL DEFAULT '',
    active_period VARCHAR(50) NOT NULL DEFAULT '',
    logo_path VARCHAR(255) DEFAULT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO ve_institution_settings (id) VALUES (1) ON DUPLICATE KEY UPDATE id=id;
