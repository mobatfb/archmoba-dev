<?php
/** La evaluación global por varios docentes se retiró. Conservar datos históricos. */
require_once __DIR__.'/../../lib/funciones.php';
exigirLogin();
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'GET') {
    http_response_code(405);
    exit('La evaluación colectiva de comportamiento ya no está disponible.');
}
redir('modulos/calificaciones/cursos.php');
