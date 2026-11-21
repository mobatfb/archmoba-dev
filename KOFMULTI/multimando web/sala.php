<?php
declare(strict_types=1);
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');
header('X-Content-Type-Options: nosniff');
header('Access-Control-Allow-Methods: GET');

function respond(int $http, array $data): never {
    http_response_code($http);
    echo json_encode($data, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}
if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    header('Allow: GET');
    respond(405, ['status' => 'error', 'message' => 'Método no permitido.']);
}
$api = 'https://api.isupol.edu.ec/api/geturlkof'; // URL fija, nunca recibe URLs del visitante.
$content = false;
if (function_exists('curl_init')) {
    $curl = curl_init($api);
    curl_setopt_array($curl, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 9,
        CURLOPT_CONNECTTIMEOUT => 4,
        CURLOPT_FOLLOWLOCATION => false,
        CURLOPT_MAXREDIRS => 0,
        CURLOPT_SSL_VERIFYPEER => true,
        CURLOPT_SSL_VERIFYHOST => 2,
        CURLOPT_HTTPHEADER => ['Accept: application/json', 'Cache-Control: no-store'],
        CURLOPT_USERAGENT => 'KOFMULTI-Web-1.0',
    ]);
    $content = curl_exec($curl);
    $http = (int)curl_getinfo($curl, CURLINFO_RESPONSE_CODE);
    curl_close($curl);
    if ($http !== 200) $content = false;
} elseif (filter_var(ini_get('allow_url_fopen'), FILTER_VALIDATE_BOOLEAN)) {
    $context = stream_context_create(['http' => [
        'timeout' => 8,
        'ignore_errors' => false,
        'follow_location' => 0,
        'header' => "Accept: application/json\r\nCache-Control: no-store\r\n",
    ]]);
    $content = @file_get_contents($api, false, $context, 0, 65536);
}
if (!is_string($content) || strlen($content) > 65536) {
    respond(503, ['status' => 'error', 'message' => 'No fue posible consultar la sala. Puedes pegar el enlace directo del anfitrión.']);
}
try { $response = json_decode($content, true, 32, JSON_THROW_ON_ERROR); }
catch (JsonException $e) { respond(502, ['status' => 'error', 'message' => 'La API devolvió datos incorrectos.']); }
if (!is_array($response) || ($response['status'] ?? '') !== 'success') {
    respond(404, ['status' => 'error', 'message' => 'No existe una sala publicada.']);
}
$data = isset($response['data']) && is_array($response['data']) ? $response['data'] : $response;
$url = trim((string)($data['url'] ?? $data['email'] ?? $response['url'] ?? $response['email'] ?? ''));
$parts = parse_url($url);
if (!is_array($parts) || !in_array(strtolower((string)($parts['scheme'] ?? '')), ['https', 'wss'], true)
    || isset($parts['user'], $parts['pass']) || isset($parts['user']) || isset($parts['port'])
    || isset($parts['query']) || isset($parts['fragment'])
    || !preg_match('/^[a-z0-9-]+\.trycloudflare\.com$/iD', (string)($parts['host'] ?? ''))) {
    respond(502, ['status' => 'error', 'message' => 'La API no contiene una dirección Cloudflare válida.']);
}
$hostname = strtolower((string)$parts['host']);
$path = $parts['path'] ?? '/';
respond(200, ['status' => 'success', 'url' => 'wss://' . $hostname . $path, 'source' => 'api']);
