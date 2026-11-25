<?php
/** Pruebas sin base de datos. Ejecutar: php tests/pruebas_resultados_cualitativos.php */
if(PHP_SAPI!=='cli'){http_response_code(403);exit;}
require_once __DIR__.'/../lib/sga_resultados_cualitativos.php';
require_once __DIR__.'/../lib/academico_integridad.php';
require_once __DIR__.'/../lib/reporte_academico_pdf.php';
require_once __DIR__.'/../lib/cuadro_anual_excel.php';
function truncar2(float $v):float{return floor(($v+1e-9)*100)/100;}
function verificar(bool $ok,string $mensaje):void{if(!$ok)throw new RuntimeException($mensaje);}
// Usar expectativas independientes del mapa de produccion, por centesima.
$rangos=[[950,1000,'A+'],[850,949,'A-'],[750,849,'B+'],[650,749,'B-'],[550,649,'C+'],[450,549,'C-'],[350,449,'D+'],[250,349,'D-'],[150,249,'E+'],[100,149,'E-'],[0,99,'E-']];
$total=0;
foreach($rangos as [$min,$max,$letra]){
    for($n=$min;$n<=$max;$n++){
        verificar(sgaLetraResultadoCualitativo($n/100)===$letra,"Equivalencia incorrecta: $n");
        verificar(sgaNotaResultadoParaConsulta($n/100,false)===number_format($n/100,2,'.',''),"Nota cuantitativa modificada: $n");
        $total++;
    }
    verificar(sgaRangoResultadoCualitativo($min/100)===number_format($min/100,2,',','').' - '.number_format($max/100,2,',',''),"Rango incorrecto: $min");
}
verificar(sgaLetraResultadoCualitativo(null)==='' && sgaNotaResultadoParaConsulta(null,true)==='—','Pendiente no puede convertirse en E-');
verificar(sgaLetraResultadoCualitativo(NAN)==='' && sgaLetraResultadoCualitativo(INF)==='','Dato no finito');
$config=['nota_aprobacion'=>7.0,'nota_min_supletorio'=>4.0];
$f=sgaResultadoAnual(9.49,9.50,9.51,null,$config);
verificar($f['promedio_tres']===9.50&&sgaLetraResultadoCualitativo($f['promedio_final'])==='A+','Promedio numerico antes de convertir');
$f=sgaResultadoAnual(6.99,6.99,6.99,8.5,$config);
verificar($f['promedio_final']===7.0&&$f['observacion']==='APROBADO'&&sgaLetraResultadoCualitativo($f['promedio_final'])==='B-','Recuperacion aprobada y letra B-');
$f=sgaResultadoAnual(6.99,6.99,6.99,null,$config);
verificar($f['observacion']==='SUPLETORIO'&&sgaLetraResultadoCualitativo($f['promedio_final'])==='B-','B- no implica aprobacion');
verificar(reporteEquivalenciaResultadoCualitativo(9.49)===['A-','8,50 - 9,49'],'Rango del certificado');
verificar(reporteEquivalencia(9.49)[0]==='D.A.R.','Certificado cuantitativo independiente');
verificar(reporteEquivalenciaComportamiento('B-')==='Próximo a alcanzar','Comportamiento sin cambios');
verificar(str_contains(cuadroAnualCeldaCalificacion('A1','B-',false,false,6.99),'s="19"'),'B- menor a siete en Excel');
verificar(str_contains(cuadroAnualCeldaCalificacion('A1','B-',false,false,7.00),'s="11"'),'B- igual a siete en Excel');
echo "OK: $total notas por centesima, rangos, pendientes, promedios, comportamiento y estilos Excel.\n";
