<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
// Generate once on the server, with no key printed or committed.
$path=__DIR__.'/config.local.php';
if(is_file($path)||getenv('SW_EVIDENCE_KEY')!==false){fwrite(STDOUT,"La clave ya existe; no se modificó.\n");exit;}
umask(0077);$f=@fopen($path,'x');if(!$f){fwrite(STDERR,"No se pudo crear la clave privada.\n");exit(1);}
try{$bytes="<?php\nif(!defined('SW_APP')){http_response_code(404);exit;}\nreturn ['key_hex'=>'".bin2hex(random_bytes(32))."'];\n";if(fwrite($f,$bytes)!==strlen($bytes))throw new RuntimeException('write');chmod($path,0600);fclose($f);echo "Clave privada creada. Respáldala en un lugar seguro.\n";}catch(Throwable $e){fclose($f);@unlink($path);fwrite(STDERR,"Error al generar la clave.\n");exit(1);}
