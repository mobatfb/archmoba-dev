<?php
// Reemplaza los datos por los que aparecen en tu panel de hosting.
// Las variables de entorno, cuando existen, tienen prioridad.
return [
    'host' => getenv('SORT_DB_HOST') ?: 'localhost',
    'port' => getenv('SORT_DB_PORT') ?: '3306',
    'database' => getenv('SORT_DB_NAME') ?: 'TUCUENTA_sorteos',
    'user' => getenv('SORT_DB_USER') !== false ? getenv('SORT_DB_USER') : 'TUCUENTA_sorteosuser',
    'password' => getenv('SORT_DB_PASSWORD') !== false ? getenv('SORT_DB_PASSWORD') : '',
];
