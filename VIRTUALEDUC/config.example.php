<?php
declare(strict_types=1);

// Copiar a config.local.php y completar los valores. No subir credenciales a GitHub.
return [
    'dsn' => 'mysql:host=localhost;dbname=virtualeduc;charset=utf8mb4',
    'db_user' => 'virtualeduc',
    'db_password' => '',
    // Sustituir por una cadena aleatoria de al menos 32 caracteres.
    // Ejemplo para generarla: php -r "echo bin2hex(random_bytes(32));"
    'install_token' => '',
];
