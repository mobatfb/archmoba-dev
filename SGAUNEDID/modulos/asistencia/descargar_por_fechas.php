<?php
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/asistencia_por_fechas_excel.php';
exigirLogin();
$ofertaId = (int)($_GET['oferta_id']??0);
if($ofertaId<=0 || !puedeGestionarOferta($ofertaId)){
    http_response_code(403);
    die('No tienes autorización para descargar la asistencia de esta asignatura.');
}
$oferta=ofertaDetalle($ofertaId);
if(!$oferta){http_response_code(404);die('La asignatura no está disponible.');}
// La asignatura debe pertenecer a un aula activa de su periodo y, en el caso
// del docente, ser una de sus ofertas activas del periodo correspondiente.
if(!esSuperadmin()){
    if(esSubadmin()){
        if(!puedeAccederPeriodo((int)$oferta['periodo_id'])){
            http_response_code(403);die('No autorizado para el período seleccionado.');
        }
    } elseif(!esDocenteOperativo((int)$oferta['periodo_id']) || (int)$oferta['docente_id']!==(int)$_SESSION['usuario_id']){
        http_response_code(403);die('No tienes acceso docente a este curso.');
    }
}
$s=$conexion->prepare('SELECT ap.activo FROM aulas_periodo ap WHERE ap.id=? AND ap.periodo_id=? LIMIT 1');
$apid=(int)$oferta['aula_periodo_id'];$pid=(int)$oferta['periodo_id'];
$s->bind_param('ii',$apid,$pid);$s->execute();$ap=$s->get_result()->fetch_assoc();$s->close();
if(!$ap || (int)$ap['activo']!==1){http_response_code(403);die('Curso no habilitado en el período.');}

$s=$conexion->prepare('SELECT id,fecha FROM asistencia_sesiones WHERE oferta_id=? ORDER BY fecha ASC,id ASC');
$s->bind_param('i',$ofertaId);$s->execute();$sesiones=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();
$s=$conexion->prepare("SELECT m.id matricula_id,m.numero_lista,m.estado matricula_estado,u.cedula,u.apellidos,u.nombres
    FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id
    WHERE m.aula_periodo_id=?
    ORDER BY COALESCE(m.numero_lista,999999),u.apellidos,u.nombres,m.id");
$s->bind_param('i',$apid);$s->execute();$estudiantes=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();
$estados=[];
$s=$conexion->prepare('SELECT ad.matricula_id,ad.sesion_id,ad.estado
    FROM asistencia_detalle ad JOIN asistencia_sesiones ss ON ss.id=ad.sesion_id
    JOIN matriculas m ON m.id=ad.matricula_id
    WHERE ss.oferta_id=? AND m.aula_periodo_id=?');
$s->bind_param('ii',$ofertaId,$apid);$s->execute();
foreach($s->get_result()->fetch_all(MYSQLI_ASSOC) as $registro){
    $estados[(int)$registro['matricula_id']][(int)$registro['sesion_id']]=(string)$registro['estado'];
}
$s->close();
try {
    $bytes=generarExcelAsistenciaPorFechas($oferta,$sesiones,$estudiantes,$estados);
    $seguro=static function($valor):string{return trim((string)preg_replace('/[^A-Za-z0-9_-]/','_', (string)$valor),'_');};
    $nombre='ASISTENCIA_FECHAS_'.$seguro($oferta['periodo']).'_'.$seguro($oferta['aula'].'_'.$oferta['paralelo']).'_'.$ofertaId.'.xlsx';
    if(function_exists('registrarAuditoria')){
        registrarAuditoria('EXPORT','Asistencia','asistencia_por_fechas',$ofertaId,
           'Se descargó la asistencia por fechas de una asignatura docente.',null,null,
           ['oferta_id'=>$ofertaId,'sesiones'=>count($sesiones),'estudiantes'=>count($estudiantes)],'exito');
    }
    if(session_status()===PHP_SESSION_ACTIVE) session_write_close();
    while(ob_get_level()>0) ob_end_clean();
    header('Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    header('Content-Disposition: attachment; filename="'.$nombre.'"');
    header('Content-Length: '.strlen($bytes));
    header('Cache-Control: private, no-store, max-age=0');
    header('X-Content-Type-Options: nosniff');
    echo $bytes;
    exit;
} catch(Throwable $e){
    error_log('SGA exportación de asistencia por fechas: '.$e->getMessage());
    http_response_code(500);
    die('No se pudo generar el Excel de asistencia por fechas.');
}
