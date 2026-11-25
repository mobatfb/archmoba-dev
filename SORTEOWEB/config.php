<?php
declare(strict_types=1);
if (!defined('SW_APP')) { http_response_code(404); exit; }
// Cambiar exclusivamente estos datos por los de cPanel.
return [
    'host' => 'localhost',
    'port' => 3306,
    'database' => 'TUCUENTA_sorteos',
    'user' => 'TUCUENTA_sorteosuser',
    'password' => '',
];
