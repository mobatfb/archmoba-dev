-- VIRTUALEDUC 0.1.3: ampliar roles sin eliminar registros.
-- Ejecutar en la base existente antes de utilizar el parche.
ALTER TABLE ve_users
    MODIFY COLUMN role ENUM('admin','subadmin','teacher','student') NOT NULL;
