<?php
/** Procesa lotes de correos pendientes del SGA. Ejecutar SOLO por CLI desde cron de hosting. */
if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit('Acceso no permitido.');
}
require_once __DIR__.'/../lib/sga_notificaciones_jornadas.php';
try {
    if (!sgaNotiTablasInstaladas()) {
        throw new RuntimeException('Instala las migraciones SQL del modulo Notificaciones.');
    }
    $resultado=sgaNotiEnviarPendientes(20);
    echo 'SGA | enviados: '.(int)$resultado['enviados'].
        '; errores: '.(int)$resultado['errores'].
        '; omitidos: '.(int)$resultado['omitidos'].PHP_EOL;
} catch (Throwable $error) {
    error_log('[SGA] Cron notificaciones: '.get_class($error));
    fwrite(STDERR, 'No se pudo procesar la cola de notificaciones.'.PHP_EOL);
    exit(1);
}
