-- VIRTUALEDUC 0.1.41: modelo de acceso y precio (USD). Ejecutar una sola vez tras 0.1.40.
ALTER TABLE courses
  ADD COLUMN access_model ENUM('free','free_paid_certificate','paid_included') NOT NULL DEFAULT 'free',
  ADD COLUMN access_price DECIMAL(10,2) NOT NULL DEFAULT 0.00;
