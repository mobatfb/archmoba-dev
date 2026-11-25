<?php
if (!defined('SW_APP') || !SW_PUBLIC) { http_response_code(404); exit; }
// Copiar a config.local.php. Completar con los datos de un buzon propio.
return [
 'transport' => 'mail', // mail (PHP/cPanel) o smtp (SMTP autenticado)
 'from_email' => '',
 'from_name' => 'SORTEOWEB',
 'smtp_host' => '',
 'smtp_port' => 587,
 'smtp_security' => 'starttls', // starttls (587) o tls (465)
 'smtp_user' => '',
 'smtp_password' => '',
];
