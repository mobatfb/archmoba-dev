<?php
declare(strict_types=1);
// Configuración de MULTIMANDO. No contiene la clave de cifrado.
// La API de Laravel lee y escribe el registro de amo_multimando.
if (!defined('MULTIMANDO_INTERNAL')) {
    http_response_code(403);
    exit;
}
return [
    'room_record_id' => 'multimandoremoteryanexx',
    'api_get_url' => 'https://api.isupol.edu.ec/api/geturlmultimando',
    'api_post_url' => 'https://api.isupol.edu.ec/api/posturlmultimando',
    // Si se establece una URL HTTPS del túnel, tiene prioridad sobre la API.
    // Dejar vacía para búsqueda automática.
    'manual_room_url' => '',
    'allowed_tunnel_domain' => '.trycloudflare.com',
];