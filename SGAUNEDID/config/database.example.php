<?php
/*
 * CONFIGURACION DE BASE DE DATOS
 *
 * En XAMPP/WAMP local normalmente funciona root sin clave.
 * En cPanel DEBES cambiar DB_USER, DB_PASS y DB_NAME por los datos
 * creados en cPanel > MySQL Databases.
 *
 * Ejemplo cPanel (NO copiar literalmente):
 *   DB_USER = 'micuenta_sgauser'
 *   DB_NAME = 'micuenta_sga_unedid'
 */
return [
    'host' => getenv('SGA_DB_HOST') ?: 'localhost',
    'port' => (int)(getenv('SGA_DB_PORT') ?: 3306),
    'user' => getenv('SGA_DB_USER') ?: 'USUARIO_MYSQL_AQUI',
    'pass' => getenv('SGA_DB_PASS') ?: 'CLAVE_MYSQL_AQUI',
    'name' => getenv('SGA_DB_NAME') ?: 'NOMBRE_MYSQL_AQUI',
];
