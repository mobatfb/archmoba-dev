-- VIRTUALEDUC 0.1.40: responsables adicionales. Los responsables actuales se conservan.
CREATE TABLE IF NOT EXISTS course_responsibles (
    course_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (course_id,user_id),
    INDEX course_responsible_user (user_id,course_id),
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
