-- SGA UNEDID | Envio por comunidad de jornada y mensajes de representantes.
-- REQUISITO: haber instalado SQL_SGA_NOTIFICACIONES_GRUPOS.sql previamente.
-- Ejecutar una vez en la misma BD del SGA. Idempotente en MariaDB 10.6+.
-- No modifica notas, matrículas, usuarios ni correos registrados.
ALTER TABLE sga_notificaciones_jornadas
  ADD COLUMN IF NOT EXISTS estudiante_contexto_id INT UNSIGNED NULL AFTER oferta_id;
SELECT 'Ampliacion de notificaciones instalada correctamente.' AS resultado;
