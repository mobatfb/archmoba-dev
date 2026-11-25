<?php
/** Validacion estructural de un volcado SQL / SQL.GZ (no equivale a restaurar).
 * Uso: php scripts/verificar_respaldo.php ruta/archivo.sql[.gz]
 * Solo lectura; no accede a la base de datos ni muestra datos personales.
 */
if(PHP_SAPI!=='cli'){http_response_code(403);exit;}
$ruta=(string)($argv[1]??'');
if($ruta===''||!is_file($ruta)||!is_readable($ruta)){
    fwrite(STDERR,"Indica una ruta SQL o SQL.GZ legible.\n");exit(2);
}
$gzip=(bool)preg_match('/\.gz$/i',$ruta);
$handle=$gzip?@gzopen($ruta,'rb'):@fopen($ruta,'rb');
if(!$handle){fwrite(STDERR,"No se pudo leer el respaldo.\n");exit(2);}
$tablas=['usuarios','usuario_roles','matriculas','calificaciones_trimestre','asistencia_sesiones','asistencia_detalle'];
$encontradas=[];$hash=hash_init('sha256');$size=0;$cola='';
while(true){
    $bloque=$gzip?gzread($handle,128*1024):fread($handle,128*1024);
    if($bloque===false){fwrite(STDERR,"Error de lectura del respaldo.\n");exit(2);}
    if($bloque==='')break;
    hash_update($hash,$bloque);$size+=strlen($bloque);
    $texto=$cola.$bloque;
    foreach($tablas as $tabla){
        if(isset($encontradas[$tabla]))continue;
        $patron='/CREATE\\s+TABLE\\s+(?:IF\\s+NOT\\s+EXISTS\\s+)?`?'.preg_quote($tabla,'/').'`?\\s*\\(/i';
        if(preg_match($patron,$texto))$encontradas[$tabla]=true;
    }
    $cola=substr($texto,-300);
}
$gzip?gzclose($handle):fclose($handle);
echo "VALIDACION ESTRUCTURAL DE RESPALDO SQL\n";
echo "Tamano analizado: $size bytes (descomprimidos si aplica)\n";
echo "SHA-256 contenido: ".hash_final($hash)."\n";
foreach($tablas as $tabla)echo (isset($encontradas[$tabla])?'OK':'FALTA')." | $tabla\n";
$correcto=count($encontradas)===count($tablas);
echo $correcto
  ?"Estructura minima detectada. PENDIENTE: comprobar restauracion real en un servidor de pruebas.\n"
  :"El respaldo no contiene todas las estructuras esperadas. Revisalo antes de instalar actualizaciones.\n";
exit($correcto?0:1);
