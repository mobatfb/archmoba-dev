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
    // AUTO consulta siempre la API. La URL manual se configura en la palanca web.
    'allowed_tunnel_domain' => '.trycloudflare.com',
];
