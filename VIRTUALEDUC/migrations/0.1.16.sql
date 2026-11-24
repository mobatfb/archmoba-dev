-- VIRTUALEDUC 0.1.16 | Ejecutar sobre la BD de v0.1.15 (tabla users sin prefijo).
-- Respaldar antes y detener temporalmente el acceso. No modifica contrasenas ni ID.
-- Conservar los cuatro roles conocidos. Los roles danados quedan sin acceso,
-- pendientes de asignacion explicita por el administrador desde Usuarios.
ALTER TABLE `users` MODIFY COLUMN `role` VARCHAR(32) NOT NULL;
UPDATE `users` SET `role`='unassigned' WHERE BINARY `role` NOT IN ('admin','subadmin','teacher','student');
ALTER TABLE `users` MODIFY COLUMN `role` ENUM('admin','subadmin','teacher','student','unassigned') NOT NULL;
