<?php
/** Ejecutar SOLO desde CLI / cPanel Cron. Nunca exponer por HTTP. */
if(PHP_SAPI!=='cli') {http_response_code(403);exit('Acceso denegado.');}
require_once dirname(__DIR__).'/lib/sga_representantes.php';
try {
    $resultado=sgaRepEnviarPendientes(30);
    echo 'Notificaciones SGA UNEDID: enviados='.(int)$resultado['enviados']
        .', errores='.(int)$resultado['errores'].', omitidos='.(int)$resultado['omitidos'].PHP_EOL;
}catch(Throwable $e){
    error_log('[SGA UNEDID] Cron representantes: '.get_class($e));
    fwrite(STDERR,"No se pudo procesar la cola de correos. Revise el error_log y SMTP.\n");
    exit(1);
}
