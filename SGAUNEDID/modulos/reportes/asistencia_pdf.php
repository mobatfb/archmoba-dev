<?php
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/reporte_asistencia_consolidado.php';
require_once __DIR__.'/../../lib/reporte_asistencia_pdf.php';
exigirLogin();
$pid=(int)($_GET['periodo_id']??0);
$apid=(int)($_GET['aula_periodo_id']??0);
$mid=(int)($_GET['matricula_id']??0);
if($pid<=0||$apid<=0){http_response_code(400);die('Selecciona un período y paralelo.');}
raExigirPeriodo($conexion,$pid);
raExigirAulaPeriodo($conexion,$apid,$pid);
$periodo=raPeriodo($conexion,$pid);
if(!$periodo){http_response_code(404);die('Período no encontrado.');}
$aulas=raListaAulas($conexion,$pid);$aula=null;
foreach($aulas as $a){if((int)$a['aula_periodo_id']===$apid){$aula=$a;break;}}
if(!$aula){http_response_code(403);die('El aula no pertenece al período o jornada autorizados.');}
[$desde,$hasta]=raRangoPeriodo($periodo,$_GET);
$datos=raCargarAula($conexion,$aula,$desde,$hasta);
if($mid>0 && !in_array($mid,array_map('intval',array_column($datos['estudiantes'],'matricula_id')),true)){
    http_response_code(403);die('El estudiante no pertenece al paralelo autorizado.');
}
try{
    $generado=raPdfGenerar($datos,(string)$periodo['nombre'],$mid>0?$mid:null);
    $pdf=$generado['pdf'];
    $nombre=$generado['nombre'];
    $vista=isset($_GET['vista']) && (string)$_GET['vista']==='1';
    registrarAuditoria('EXPORT','Asistencia','reporte_asistencia_pdf',$mid>0?$mid:$apid,
        'Reporte consolidado de asistencia del paralelo '.raPdfTituloAula($aula).' · '.$desde.' a '.$hasta.'.',
        null,null,['periodo_id'=>$pid,'aula_periodo_id'=>$apid,'matricula_id'=>$mid,'desde'=>$desde,'hasta'=>$hasta], 'exito');
    if(session_status()===PHP_SESSION_ACTIVE)session_write_close();
    while(ob_get_level()>0)ob_end_clean();
    header('Cache-Control: private, no-store, max-age=0');
    $pdf->output($nombre,$vista);
}catch(Throwable $e){
    error_log('SGA Reporte asistencia PDF: '.$e->getMessage());
    http_response_code(500);die('No se pudo generar el reporte de asistencia.');
}
