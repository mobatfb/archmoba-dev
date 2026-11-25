<?php
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
define('SW_APP',true);date_default_timezone_set('America/Guayaquil');
require dirname(__DIR__).'/core/database.php';require dirname(__DIR__).'/core/helpers.php';require __DIR__.'/service.php';
try{echo 'Sorteos cerrados: '.draw_process_due().PHP_EOL;}catch(Throwable $e){fwrite(STDERR,'SORTEOWEB: cierre no ejecutado. Revise migracion y clave privada.'.PHP_EOL);exit(1);}
