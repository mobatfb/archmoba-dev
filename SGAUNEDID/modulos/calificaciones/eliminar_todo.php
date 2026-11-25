<?php
require_once __DIR__.'/../../lib/funciones.php';
exigirLogin();
if ($_SERVER['REQUEST_METHOD']!=='POST') { http_response_code(405);die('Método no permitido.'); }
$oid=(int)($_POST['oferta_id']??0);
$trim=(int)($_POST['trimestre']??0);
if (!$oid || $trim<1 || $trim>3 || !puedeGestionarOferta($oid)) {
    http_response_code(403);die('Operación no permitida.');
}
if (empty($_SESSION['csrf_calificaciones']) || !hash_equals($_SESSION['csrf_calificaciones'],(string)($_POST['csrf']??''))) {
    http_response_code(403);die('Solicitud inválida. Recarga la página.');
}
if (!hash_equals('ELIMINAR',(string)($_POST['confirmacion']??''))) {
    flash('error','La eliminación total requiere confirmación escribiendo ELIMINAR.');
    redir('modulos/calificaciones/index.php?oferta_id='.$oid.'&trimestre='.$trim);
}
impedirNotasEnVisorComportamiento($oid);$o=ofertaDetalle($oid);
$eliminados=0;
try {
    sgaAsegurarPeriodoEditable((int)$o['periodo_id']);
    $conexion->begin_transaction();
    $stmt=$conexion->prepare('DELETE c FROM calificaciones_trimestre c JOIN matriculas m ON m.id=c.matricula_id WHERE c.oferta_id=? AND c.trimestre=? AND m.aula_periodo_id=?');
    $apid=(int)$o['aula_periodo_id'];
    $stmt->bind_param('iii',$oid,$trim,$apid);
    if (!$stmt->execute()) throw new RuntimeException('No fue posible eliminar los registros.');
    $eliminados=$stmt->affected_rows;
    $stmt->close();
    sgaAuditoriaObligatoria('DELETE','Calificaciones','oferta_academica',$oid,'Eliminación total de las calificaciones del trimestre '.$trim.'.',null,null,['oferta_id'=>$oid,'trimestre'=>$trim,'registros_eliminados'=>$eliminados],'exito',null,null,'critica');
    if(!$conexion->commit())throw new RuntimeException('No se pudo confirmar el borrado.');
    flash('success',"Se limpiaron $eliminados registros de calificaciones del trimestre $trim. Se conservaron las calificaciones de otras asignaturas.");
} catch(Throwable $e) {
    try {$conexion->rollback();} catch(Throwable $ignored) {}
    registrarAuditoria('DELETE','Calificaciones','oferta_academica',$oid,'Falló la eliminación total: '.$e->getMessage(),null,null,['trimestre'=>$trim],'fallo',null,null,'critica');
    flash('error','No se pudo limpiar todo: '.$e->getMessage());
}
redir('modulos/calificaciones/index.php?oferta_id='.$oid.'&trimestre='.$trim);
