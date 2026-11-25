<?php
/** Copiar como recuperacion.php solo en la instalacion local; no subir las credenciales a Git. */
return [
    'app_url' => getenv('SGA_APP_URL') ?: 'https://sga.example.com',
    'smtp' => [
        'host' => getenv('SGA_SMTP_HOST') ?: 'smtp.example.com',
        'port' => (int)(getenv('SGA_SMTP_PORT') ?: 465),
        'security' => getenv('SGA_SMTP_SECURITY') ?: 'ssl',
        'username' => getenv('SGA_SMTP_USER') ?: '',
        'password' => getenv('SGA_SMTP_PASS') ?: '',
        'from' => getenv('SGA_SMTP_FROM') ?: '',
        'from_name' => 'Sistema de Gestión Académica UNEDID',
        'timeout' => 10,
    ],
    // Generar un secreto propio: php -r 'echo bin2hex(random_bytes(32)), PHP_EOL;'
    'rate_secret' => getenv('SGA_RATE_SECRET') ?: '',
];
