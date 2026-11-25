<?php
/** Foto personal privada: solo para la cuenta autenticada, nunca URL de disco. */
require_once __DIR__ . '/../../lib/funciones.php';
require_once __DIR__ . '/../../lib/foto_perfil_privada.php';

header('Cache-Control: private, no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');
header('X-Content-Type-Options: nosniff');
header('Cross-Origin-Resource-Policy: same-origin');
header('Referrer-Policy: no-referrer');
header('X-Frame-Options: DENY');

// Antes de devolver cualquier byte se comprueba la sesion y cuenta activa.
if (empty($_SESSION['usuario_id'])) {
    http_response_code(403);
    exit;
}
exigirLogin();
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'GET') {
    http_response_code(405);
    header('Allow: GET');
    exit;
}
// Evita el hotlinking y las peticiones desde otras paginas del navegador.
if (isset($_SERVER['HTTP_SEC_FETCH_SITE']) &&
    $_SERVER['HTTP_SEC_FETCH_SITE'] !== 'same-origin') {
    http_response_code(403);
    exit;
}
// Si el navegador envia Fetch Metadata, solo se atiende la etiqueta <img>.
if (isset($_SERVER['HTTP_SEC_FETCH_DEST']) &&
    $_SERVER['HTTP_SEC_FETCH_DEST'] !== 'image') {
    http_response_code(403);
    exit;
}
$usuario = usuarioActual();
$ruta = $usuario ? sgaPerfilRutaFoto($usuario) : null;
if (!$ruta || !is_file($ruta) || is_link($ruta) || !is_readable($ruta)) {
    http_response_code(404);
    exit;
}
$size = @filesize($ruta);
if ($size === false || $size < 8 || $size > 1048576) {
    http_response_code(404);
    exit;
}
// Se exige firma PNG; no se sirve contenido subido en otro formato.
$fh = @fopen($ruta, 'rb');
if (!$fh) { http_response_code(404); exit; }
$firma = fread($fh, 8);
if ($firma !== "\x89PNG\r\n\x1a\n") { fclose($fh); http_response_code(404); exit; }
header('Content-Type: image/png');
header('Content-Length: ' . $size);
header('Content-Disposition: inline; filename="foto-perfil.png"');
rewind($fh);
fpassthru($fh);
fclose($fh);
