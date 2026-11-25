<?php
if (session_status() !== PHP_SESSION_ACTIVE) {
    session_start();
}

date_default_timezone_set('America/Guayaquil');

define('APP_NAME', 'Sistema de Gestión Académica UNEDID');
define('APP_ROOT', dirname(__DIR__));
$docRoot = isset($_SERVER['DOCUMENT_ROOT']) ? realpath($_SERVER['DOCUMENT_ROOT']) : false;
$appRoot = realpath(APP_ROOT);
$appUrl = '';
if ($docRoot && $appRoot) {
    $appNorm = str_replace('\\', '/', $appRoot);
    $docNorm = str_replace('\\', '/', $docRoot);
    if (strpos($appNorm, $docNorm) === 0) {
        $appUrl = substr($appNorm, strlen($docNorm));
    }
}
define('APP_URL', rtrim($appUrl, '/'));

function url(string $ruta = ''): string {
    return APP_URL . '/' . ltrim($ruta, '/');
}
