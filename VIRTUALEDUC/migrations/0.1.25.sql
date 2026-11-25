-- VIRTUALEDUC 0.1.25 | Ejecutar una sola vez sobre v0.1.24.
-- Respaldar la base de datos y detener el acceso antes de importar.
ALTER TABLE courses
    ADD COLUMN modality VARCHAR(20) NULL,
    ADD COLUMN duration_hours DECIMAL(7,2) NULL,
    ADD COLUMN level VARCHAR(20) NULL,
    ADD COLUMN period VARCHAR(50) NOT NULL DEFAULT '',
    ADD COLUMN thumbnail_variant TINYINT UNSIGNED NOT NULL DEFAULT 1,
    ADD COLUMN thumbnail_path VARCHAR(255) NULL;
UPDATE courses SET thumbnail_variant=MOD(id,3)+1;
CREATE TABLE course_modules (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_id BIGINT UNSIGNED NOT NULL,
    title VARCHAR(180) NOT NULL,
    position INT UNSIGNED NOT NULL DEFAULT 1,
    UNIQUE KEY course_module_position (course_id,position),
    UNIQUE KEY course_module_identity (course_id,id),
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO course_modules(course_id,title,position) SELECT id,'Módulo 1',1 FROM courses;
ALTER TABLE lessons ADD COLUMN module_id BIGINT UNSIGNED NULL AFTER course_id;
UPDATE lessons l JOIN course_modules m ON m.course_id=l.course_id AND m.position=1 SET l.module_id=m.id;
ALTER TABLE lessons MODIFY COLUMN module_id BIGINT UNSIGNED NOT NULL,
    ADD CONSTRAINT lessons_course_module_fk FOREIGN KEY (course_id,module_id) REFERENCES course_modules(course_id,id) ON DELETE CASCADE;
