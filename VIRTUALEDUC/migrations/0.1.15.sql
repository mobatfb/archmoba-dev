-- VIRTUALEDUC 0.1.15 | Ejecutar UNA sola vez sobre v0.1.14.
-- Hacer respaldo, detener el acceso al sistema y seleccionar la BD existente.
-- Si alguna tabla de destino ya existe, resolver el conflicto antes de ejecutar.
-- Un solo RENAME TABLE conserva los datos y las relaciones InnoDB.
RENAME TABLE
    `ve_users` TO `users`,
    `ve_courses` TO `courses`,
    `ve_lessons` TO `lessons`,
    `ve_enrollments` TO `enrollments`,
    `ve_progress` TO `progress`,
    `ve_institution_settings` TO `institution_settings`;
