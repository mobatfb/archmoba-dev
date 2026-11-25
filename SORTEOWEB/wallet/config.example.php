<?php
if (!defined('SW_APP') || !SW_PUBLIC) { http_response_code(404); exit; }
// Copiar a config.local.php SOLO en el servidor. No subir credenciales a GitHub.
// NO activar mientras no exista autorizacion escrita de PayPhone para este modelo,
// revision legal/fiscal y un flujo de compra, devoluciones y conciliacion probado.
return [
    'enabled' => false,
    'merchant_authorized' => false,
    'token' => '',
    'store_id' => '',
    'base_url' => 'https://tiendavibechic.com/sorteos/',
    'min_cents' => 100,
    'max_cents' => 5000,
];
