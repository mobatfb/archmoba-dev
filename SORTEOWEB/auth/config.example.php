<?php
if (!defined('SW_APP') || !SW_PUBLIC) { http_response_code(404); exit; }
// Copiar a config.local.php. Generar con php -r 'echo bin2hex(random_bytes(32)), PHP_EOL;'
return ['otp_secret' => ''];
