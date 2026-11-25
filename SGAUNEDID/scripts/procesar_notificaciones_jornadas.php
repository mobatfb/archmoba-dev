<?php
/** Solo CLI / Cron de cPanel; nunca ejecutar via URL publica. */
if (PHP_SAPI !== 'cli') { http_response_code(403); exit('Acceso denegado.'); }
require_once dirname(__DIR__).'/lib/sga_notificaciones_jornadas.php';
try {
    $r=sgaNotiEnviarPendientes(30);
    echo 'Notificaciones por jornada: enviados='.(int)$r['enviados'].
        ', errores='.(int)$r['errores'].', omitidos='.(int)$r['omitidos'].PHP_EOL;
} catch (Throwable $e) {
    error_log('[SGA UNEDID] Cron notificaciones jornadas: '.get_class($e));
    fwrite(STDERR,"No fue posible procesar la cola. Revisar configuracion SMTP y registro de errores.\n");
    exit(1);
}
