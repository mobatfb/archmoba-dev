<?php
/** Pruebas autocontenidas de notas anuales; sin conexion ni datos reales. */
if(PHP_SAPI!=='cli'){http_response_code(403);exit;}
function truncar2(float $v):float{return floor(($v+1e-9)*100)/100;}
require_once __DIR__.'/../lib/academico_integridad.php';
$config=['nota_aprobacion'=>7.0,'nota_min_supletorio'=>4.0];
function verificar(bool $ok,string $caso):void{
    if(!$ok){fwrite(STDERR,"FALLO: $caso\n");exit(1);}
    echo "OK: $caso\n";
}
$pendiente=sgaResultadoAnual(8.0,null,null,null,$config);
verificar($pendiente['promedio_final']===null&&$pendiente['observacion']==='EN CURSO','Trimestres sin registrar no son cero');
$aprobado=sgaResultadoAnual(7.0,7.0,7.0,null,$config);
verificar($aprobado['promedio_final']===7.0&&$aprobado['observacion']==='APROBADO','Aprobacion ordinaria');
$suplemento=sgaResultadoAnual(5.0,6.0,4.0,null,$config);
verificar($suplemento['promedio_tres']===5.0&&$suplemento['observacion']==='SUPLETORIO','Supletorio pendiente mantiene promedio');
$suplementoAprobado=sgaResultadoAnual(5.0,6.0,4.0,9.0,$config);
verificar($suplementoAprobado['promedio_final']===7.0&&$suplementoAprobado['observacion']==='APROBADO','Supletorio aprobado');
$reprobado=sgaResultadoAnual(2.0,3.0,2.0,null,$config);
verificar($reprobado['observacion']==='REPROBADO','No autoriza supletorio fuera del rango');
foreach([
  [null,6.0,6.0,7.0,'sin tres trimestres'],
  [9.0,8.0,9.0,7.0,'alumno ya aprobado'],
  [2.0,3.0,2.0,7.0,'promedio menor al minimo'],
  [5.0,6.0,4.0,0.0,'nota suplementaria cero'],
  [5.0,6.0,4.0,11.0,'nota suplementaria mayor a 10'],
] as [$t1,$t2,$t3,$sup,$caso]){
  $rechazado=false;
  try{sgaValidarSupletorio($t1,$t2,$t3,$sup,$config);}catch(DomainException $e){$rechazado=true;}
  verificar($rechazado,'Validacion supletorio: '.$caso);
}
sgaValidarSupletorio(5.0,6.0,4.0,7.0,$config);
verificar(true,'Supletorio valido');
echo "INTEGRIDAD ACADEMICA: TODAS LAS PRUEBAS PASARON\n";
