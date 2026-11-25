<?php
require_once __DIR__.'/../../lib/funciones.php';
exigirLogin();
if ($_SERVER['REQUEST_METHOD']!=='POST') redir('dashboard.php');
$oid=(int)($_POST['oferta_id']??0);
$trim=(int)($_POST['trimestre']??0);
$mid=(int)($_POST['matricula_id']??0);
if (!$oid || !$mid || $trim<1 || $trim>3 || !puedeGestionarOferta($oid)) {
    http_response_code(403);die('No tienes acceso a esta operación.');
}
if (empty($_SESSION['csrf_calificaciones']) || !hash_equals($_SESSION['csrf_calificaciones'],(string)($_POST['csrf']??''))) {
    http_response_code(403);die('Solicitud inválida. Recarga la página.');
}
impedirNotasEnVisorComportamiento($oid);$o=ofertaDetalle($oid);
try {
    sgaAsegurarPeriodoEditable((int)$o['periodo_id']);
    $conexion->begin_transaction();
    $stmt=$conexion->prepare('SELECT c.*,m.estudiante_id,u.apellidos,u.nombres FROM calificaciones_trimestre c JOIN matriculas m ON m.id=c.matricula_id JOIN usuarios u ON u.id=m.estudiante_id WHERE c.oferta_id=? AND c.matricula_id=? AND c.trimestre=? AND m.aula_periodo_id=? LIMIT 1');
    $apid=(int)$o['aula_periodo_id'];
    $stmt->bind_param('iiii',$oid,$mid,$trim,$apid);$stmt->execute();$antes=$stmt->get_result()->fetch_assoc();$stmt->close();
    if (!$antes) throw new RuntimeException('El estudiante todavía no tiene notas guardadas en este trimestre.');
    $stmt=$conexion->prepare('DELETE FROM calificaciones_trimestre WHERE oferta_id=? AND matricula_id=? AND trimestre=?');
    $stmt->bind_param('iii',$oid,$mid,$trim);
    if (!$stmt->execute()) throw new RuntimeException('No se pudo eliminar el registro.');
    $stmt->close();
    sgaAuditoriaObligatoria('DELETE','Calificaciones','calificacion_trimestre',$antes['id'],'Registro de calificaciones eliminado para '.$antes['apellidos'].' '.$antes['nombres'].' · '.$o['asignatura'].' · T'.$trim.'.',(int)$antes['estudiante_id'],$antes,null,'exito',null,null,'critica');
    if(!$conexion->commit())throw new RuntimeException('No se confirmo la eliminación del trimestre.');
    flash('success','Calificaciones del estudiante eliminadas para el trimestre '.$trim.'.');
} catch(Throwable $e) {
    try{$conexion->rollback();}catch(Throwable $ignorada){}
    flash('error','No se pudo limpiar la fila: '.$e->getMessage());
}
redir('modulos/calificaciones/index.php?oferta_id='.$oid.'&trimestre='.$trim);
