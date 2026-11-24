-- VIRTUALEDUC 0.1.12 | Ejecutar UNA sola vez sobre v0.1.11, despues de un respaldo.
ALTER TABLE ve_users
    ADD COLUMN username VARCHAR(190) NULL AFTER id,
    ADD COLUMN first_names VARCHAR(150) NOT NULL DEFAULT '' AFTER name,
    ADD COLUMN last_names VARCHAR(150) NOT NULL DEFAULT '' AFTER first_names,
    ADD UNIQUE KEY ve_users_username_unique (username);

-- El administrador inicial mantiene admin; las cuentas anteriores conservan su correo como usuario.
-- No se intenta dividir nombres antiguos automaticamente.
UPDATE ve_users SET username=CASE WHEN email='admin@virtualeduc.local' AND role='admin' THEN 'admin' ELSE email END,
    first_names=name WHERE username IS NULL;
