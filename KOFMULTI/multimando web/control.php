<?php
declare(strict_types=1);
/* El navegador recibe JavaScript desencriptado. El código sigue siendo inspeccionable.
   No se incluye el código fuente original en el paquete público. */
header('Content-Type: text/javascript; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');

function failed(string $message): never {
    http_response_code(503);
    echo 'console.error(' . json_encode('KOFMULTI: ' . $message, JSON_UNESCAPED_UNICODE) . ');';
    exit;
}
$secretFile = __DIR__ . '/private/FRASE_CIFRADO.php';
$encryptedFile = __DIR__ . '/private/control.enc';
if (!is_file($secretFile) || !is_file($encryptedFile)) failed('Falta el módulo cifrado o su frase privada.');
if (!function_exists('openssl_decrypt') || !function_exists('gzdecode')) failed('Este hosting necesita OpenSSL y zlib para PHP.');
define('KOF_PRIVATE_INCLUDE', true);
$phrase = require $secretFile;
if (!is_string($phrase) || strlen($phrase) < 30) failed('Frase de cifrado no configurada.');
$raw = file_get_contents($encryptedFile);
if ($raw === false || strlen($raw) > 131072) failed('Archivo cifrado no disponible.');
try { $record = json_decode($raw, true, 8, JSON_THROW_ON_ERROR); }
catch (JsonException $e) { failed('Formato de cifrado incorrecto.'); }
if (!is_array($record) || ($record['v'] ?? null) !== 1) failed('Versión de cifrado no compatible.');
$iv = base64_decode((string)($record['iv'] ?? ''), true);
$tag = base64_decode((string)($record['tag'] ?? ''), true);
$ciphertext = base64_decode((string)($record['cipher'] ?? ''), true);
if ($iv === false || strlen($iv) !== 12 || $tag === false || strlen($tag) !== 16 || $ciphertext === false) failed('Datos cifrados dañados.');
$key = hash('sha256', $phrase, true);
$compressed = openssl_decrypt($ciphertext, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $iv, $tag);
if (!is_string($compressed)) failed('No se pudo descifrar el módulo. Revisa la frase.');
$script = gzdecode($compressed);
if (!is_string($script) || strlen($script) > 200000) failed('Código descifrado inválido.');
header('Content-Length: ' . strlen($script));
echo $script;
