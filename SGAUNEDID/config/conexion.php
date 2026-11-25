<?php
require_once __DIR__ . '/app.php';

$db = require __DIR__ . '/database.php';

// PHP 8.1+ puede lanzar mysqli_sql_exception por defecto. Desactivamos el
// modo estricto para controlar el error y evitar una pantalla HTTP 500 vacia.
mysqli_report(MYSQLI_REPORT_OFF);

$conexion = @new mysqli(
    (string)$db['host'],
    (string)$db['user'],
    (string)$db['pass'],
    (string)$db['name'],
    (int)$db['port']
);

if ($conexion->connect_errno) {
    $detalle = 'MySQL error ' . $conexion->connect_errno . ': ' . $conexion->connect_error;
    error_log('[SGA UNEDID] Error de conexion BD. ' . $detalle);
    http_response_code(503);
    $archivo = htmlspecialchars(__DIR__ . '/database.php', ENT_QUOTES, 'UTF-8');
    die(
        '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'.
        '<title>Configuracion pendiente - SGA UNEDID</title>'.
        '<style>body{font-family:Arial,sans-serif;background:#f3f6fa;color:#152033;padding:32px}.box{max-width:760px;margin:40px auto;background:#fff;border:1px solid #dce4ee;border-radius:14px;padding:24px}code{background:#eef4fb;padding:2px 5px;border-radius:4px}.bad{color:#a32929;font-weight:700}</style></head><body><div class="box">'.
        '<h1>No se pudo conectar con la base de datos</h1>'.
        '<p>El sistema esta cargando, pero la conexion MySQL del hosting no coincide con la configuracion actual.</p>'.
        '<p>Revise <code>config/database.php</code> y coloque el <strong>usuario, clave y nombre de base de datos de cPanel</strong>.</p>'.
        '<p>Tambien confirme en cPanel que el usuario MySQL esta agregado a la base con <strong>ALL PRIVILEGES</strong>.</p>'.
        '<p class="bad">Por seguridad, el detalle tecnico completo se envio al error_log del servidor.</p>'.
        '</div></body></html>'
    );
}

if (!$conexion->set_charset('utf8mb4')) {
    error_log('[SGA UNEDID] No se pudo establecer utf8mb4: ' . $conexion->error);
}
