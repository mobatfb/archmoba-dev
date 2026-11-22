<?php
declare(strict_types=1);
// En el navegador el JavaScript descifrado sigue siendo inspeccionable.
header('Content-Type: text/javascript; charset=utf-8');
header('Cache-Control: private, no-store');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
function fail_script(string $message): never {
    http_response_code(503);
    echo 'console.error(' . json_encode('MULTIMANDO: ' . $message, JSON_UNESCAPED_UNICODE) . ');';
    exit;
}
$secret = __DIR__ . '/private/FRASE_CIFRADO.php';
$encrypted = __DIR__ . '/private/palanca.enc';
if (!is_file($secret) || !is_file($encrypted)) fail_script('Falta la frase privada o el módulo cifrado.');
if (!function_exists('openssl_decrypt') || !function_exists('gzdecode')) fail_script('PHP requiere OpenSSL y zlib.');
define('MULTIMANDO_PRIVATE_INCLUDE', true);
$phrase = require $secret;
if (!is_string($phrase) || strlen($phrase) < 40) fail_script('Frase inválida.');
$raw = file_get_contents($encrypted);
if ($raw === false || strlen($raw) > 150000) fail_script('Archivo cifrado incorrecto.');
try { $record = json_decode($raw, true, 8, JSON_THROW_ON_ERROR); }
catch (JsonException $e) { fail_script('Archivo cifrado dañado.'); }
if (!is_array($record) || ($record['v'] ?? null) !== 1) fail_script('Formato de cifrado incorrecto.');
$iv = base64_decode((string)($record['iv'] ?? ''), true);
$tag = base64_decode((string)($record['tag'] ?? ''), true);
$cipher = base64_decode((string)($record['cipher'] ?? ''), true);
if ($iv === false || strlen($iv) !== 12 || $tag === false || strlen($tag) !== 16 || $cipher === false)
    fail_script('Datos cifrados inválidos.');
$key = hash('sha256', $phrase, true);
$zipped = openssl_decrypt($cipher, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $iv, $tag);
if (!is_string($zipped)) fail_script('No se pudo descifrar. Revisa la frase.');
$js = gzdecode($zipped);
if (!is_string($js) || strlen($js) > 200000) fail_script('JavaScript descifrado no válido.');
header('Content-Length: ' . strlen($js));
echo $js;
