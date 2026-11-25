<?php
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/asistencia_excel.php';
exigirLogin();
$oid=(int)($_GET['oferta_id']??0);
if(!$oid || !puedeGestionarOferta($oid)){http_response_code(403);die('No tienes acceso a esta asignación.');}
$o=ofertaDetalle($oid);
if(!$o){http_response_code(404);die('Asignación inexistente.');}
$fecha=trim((string)($_GET['fecha']??''));
$d=DateTime::createFromFormat('!Y-m-d',$fecha);
if(!$d || $d->format('Y-m-d')!==$fecha){http_response_code(400);die('Fecha de asistencia inválida.');}
$stmt=$conexion->prepare('SELECT id,fecha,tema,observaciones,registrado_por FROM asistencia_sesiones WHERE oferta_id=? AND fecha=? LIMIT 1');
$stmt->bind_param('is',$oid,$fecha);$stmt->execute();$sesion=$stmt->get_result()->fetch_assoc()?:null;$stmt->close();
if(!$sesion){
    flash('error','Primero guarda la asistencia de esa fecha para poder exportarla a Excel.');
    redir('modulos/asistencia/registro.php?oferta_id='.$oid.'&fecha='.urlencode($fecha));
}
$sid=(int)$sesion['id'];$apid=(int)$o['aula_periodo_id'];
$stmt=$conexion->prepare("SELECT m.numero_lista,u.cedula,u.apellidos,u.nombres,ad.estado,ad.observacion
    FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id
    LEFT JOIN asistencia_detalle ad ON ad.sesion_id=? AND ad.matricula_id=m.id
    WHERE m.aula_periodo_id=? AND m.estado='activo'
    ORDER BY COALESCE(m.numero_lista,9999),u.apellidos,u.nombres");
$stmt->bind_param('ii',$sid,$apid);$stmt->execute();$estudiantes=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
$tmp=null;
try{
    $generado=generarExcelAsistencia($o,$sesion,$estudiantes);
    $tmp=$generado['archivo'];
    $codigo=trim((string)($o['asignatura_codigo']??''));
    if($codigo==='')$codigo='ASIGNATURA_'.$oid;
    $codigo=preg_replace('/[^A-Za-z0-9_-]+/','_',iconv('UTF-8','ASCII//TRANSLIT//IGNORE',$codigo)?:$codigo);
    $nombre='ASISTENCIA_'.substr($codigo,0,32).'_'.$fecha.'_OFERTA'.$oid.'.xlsx';
    registrarAuditoria('EXPORT','Asistencia','asistencia_excel',$sid,
        'Exportación de asistencia a Excel · '.$o['asignatura'].' · '.$fecha.'.',
        null,null,['oferta_id'=>$oid,'fecha'=>$fecha,'estudiantes'=>count($estudiantes),'resumen'=>$generado['resumen']],
        'exito',null,null,'info');
    if(session_status()===PHP_SESSION_ACTIVE)session_write_close();
    while(ob_get_level()>0)ob_end_clean();
    header('Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    header('Content-Disposition: attachment; filename="'.$nombre.'"');
    header('Content-Length: '.(int)filesize($tmp));
    header('Cache-Control: private, no-store, no-cache, must-revalidate');
    header('X-Content-Type-Options: nosniff');
    readfile($tmp);
    @unlink($tmp);
    exit;
}catch(Throwable $e){
    if($tmp!==null)@unlink($tmp);
    error_log('Error de exportación de asistencia Excel: '.$e->getMessage());
    flash('error','No se pudo generar el Excel de asistencia. Inténtalo nuevamente o comunícate con el administrador.');
    redir('modulos/asistencia/registro.php?oferta_id='.$oid.'&fecha='.urlencode($fecha));
}
