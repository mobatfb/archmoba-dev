<?php
declare(strict_types=1);
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate');
header('X-Content-Type-Options: nosniff');
header('Access-Control-Allow-Methods: GET');
function reply(int $code, array $data): never {
    http_response_code($code);
    echo json_encode($data, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'GET') {
    header('Allow: GET');
    reply(405, ['status' => 'error', 'message' => 'Solo se admite GET.']);
}
define('MULTIMANDO_INTERNAL', true);
$config = require __DIR__ . '/config.php';

function safe_websocket_url(string $raw, string $suffix): ?string {
    $raw = trim($raw);
    if ($raw === '' || strlen($raw) > 512) return null;
    $url = parse_url($raw);
    if (!is_array($url)) return null;
    $scheme = strtolower((string)($url['scheme'] ?? ''));
    if (!in_array($scheme, ['https', 'wss'], true)) return null;
    if (isset($url['user']) || isset($url['pass']) || isset($url['port']) ||
        isset($url['query']) || isset($url['fragment'])) return null;
    $host = strtolower((string)($url['host'] ?? ''));
    if (!preg_match('/^[a-z0-9-]+\.trycloudflare\.com$/D', $host)) return null;
    if (!str_ends_with($host, $suffix)) return null;
    $path = (string)($url['path'] ?? '/');
    return 'wss://' . $host . ($path !== '' ? $path : '/');
}

// Modo AUTO: consultar SIEMPRE la API fija. La URL manual sólo se usa en el navegador.
$api = (string)($config['api_get_url'] ?? '');
if ($api !== 'https://api.isupol.edu.ec/api/geturlmultimando') {
    reply(500, ['status' => 'error', 'message' => 'API no permitida.']);
}
$body = false;
if (function_exists('curl_init')) {
    $ch = curl_init($api);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 9,
        CURLOPT_CONNECTTIMEOUT => 4,
        CURLOPT_FOLLOWLOCATION => false,
        CURLOPT_SSL_VERIFYPEER => true,
        CURLOPT_SSL_VERIFYHOST => 2,
        CURLOPT_HTTPHEADER => ['Accept: application/json', 'Cache-Control: no-store'],
        CURLOPT_USERAGENT => 'MULTIMANDO-WEB/1.0',
    ]);
    $body = curl_exec($ch);
    $http = (int)curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    curl_close($ch);
    if ($http !== 200) $body = false;
} else {
    $ctx = stream_context_create(['http' => [
        'timeout' => 8,
        'follow_location' => 0,
        'header' => "Accept: application/json\r\nCache-Control: no-store\r\n",
    ], 'ssl' => ['verify_peer' => true, 'verify_peer_name' => true]]);
    $body = @file_get_contents($api, false, $ctx, 0, 65536);
}
if (!is_string($body) || strlen($body) > 65536) {
    reply(503, ['status' => 'error', 'message' => 'No fue posible consultar la API de MULTIMANDO.']);
}
try { $payload = json_decode($body, true, 12, JSON_THROW_ON_ERROR); }
catch (JsonException $e) { reply(502, ['status' => 'error', 'message' => 'Respuesta JSON incorrecta.']); }
if (!is_array($payload) || ($payload['status'] ?? '') !== 'success') {
    reply(502, ['status' => 'error', 'message' => 'La API no devolvió una sala válida.']);
}
$record = is_array($payload['data'] ?? null) ? $payload['data'] : $payload;
$url = safe_websocket_url((string)($record['url'] ?? $record['email'] ?? $payload['url'] ?? ''),
    (string)$config['allowed_tunnel_domain']);
if ($url === null) {
    reply(404, ['status' => 'error', 'message' => 'No hay anfitrión publicado en MULTIMANDO.']);
}
reply(200, ['status' => 'success', 'url' => $url, 'source' => 'api']);