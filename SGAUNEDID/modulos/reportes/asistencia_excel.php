<?php
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/reporte_asistencia_consolidado.php';
require_once __DIR__.'/../../lib/reporte_asistencia_excel.php';
exigirLogin();
$pid=(int)($_GET['periodo_id']??0);
$apid=(int)($_GET['aula_periodo_id']??0);
$todos=isset($_GET['todos']) && (string)$_GET['todos']==='1';
if($pid<=0){http_response_code(400);die('Selecciona un período académico.');}
raExigirPeriodo($conexion,$pid);
$periodo=raPeriodo($conexion,$pid);
if(!$periodo){http_response_code(404);die('Período no encontrado.');}
[$desde,$hasta]=raRangoPeriodo($periodo,$_GET);
$aulas=raListaAulas($conexion,$pid);
if(!$todos){
    raExigirAulaPeriodo($conexion,$apid,$pid);
    $aulas=array_values(array_filter($aulas,static fn($a)=>(int)$a['aula_periodo_id']===$apid));
    if(!$aulas){http_response_code(403);die('El paralelo no corresponde al período o jornada autorizados.');}
}
if(!$aulas){http_response_code(404);die('No hay aulas autorizadas para generar este Excel.');}
$datos=[];
foreach($aulas as $a)$datos[]=raCargarAula($conexion,$a,$desde,$hasta);
try{
    $archivo=raXlsxLibro($datos,(string)$periodo['nombre']);
    registrarAuditoria('EXPORT','Asistencia','reporte_asistencia_periodo',$pid,
        'Reporte consolidado Excel de asistencia '.($todos?'por período':'por paralelo').'.',
        null,null,['periodo_id'=>$pid,'aulas'=>count($datos),'desde'=>$desde,'hasta'=>$hasta], 'exito');
    $slug=preg_replace('/[^A-Za-z0-9_-]/','_',(string)$periodo['nombre'])?:'PERIODO';
    $nombre='ASISTENCIA_'.$slug.($todos?'_AULAS':'_PARALELO_'.$apid).'.xlsx';
    if(session_status()===PHP_SESSION_ACTIVE)session_write_close();
    while(ob_get_level()>0)ob_end_clean();
    header('Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    header('Content-Disposition: attachment; filename="'.$nombre.'"');
    header('Content-Length: '.strlen($archivo));
    header('Cache-Control: private, no-store, max-age=0');
    header('X-Content-Type-Options: nosniff');
    echo $archivo;
    exit;
}catch(Throwable $e){
    error_log('SGA Reporte asistencia Excel: '.$e->getMessage());
    http_response_code(500);die('No se pudo generar el Excel consolidado de asistencia.');
}
