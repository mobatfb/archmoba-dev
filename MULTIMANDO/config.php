<?php
declare(strict_types=1);
// Sólo la palanca web: lectura de la URL pública de MULTIMANDO.
// La publicación (POST), la cola y los turnos los gestiona el anfitrión Python.
if (!defined('MULTIMANDO_INTERNAL')) {
    http_response_code(403);
    exit;
}
return [
    'api_get_url' => 'https://api.isupol.edu.ec/api/geturlmultimando',
    // Opcional: enlace directo HTTPS de Cloudflare para pruebas, sin usar la API.
    'manual_room_url' => '',
    'allowed_tunnel_domain' => '.trycloudflare.com',
];