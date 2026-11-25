<?php
/** Quita exclusivamente un registro de supletorio; no toca las notas trimestrales. */
require_once __DIR__.'/../../lib/sga_supletorios.php';
exigirLogin();
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); exit('Método no permitido.'); }
$ofertaId = (int)($_POST['oferta_id'] ?? 0);
$matriculaId = (int)($_POST['matricula_id'] ?? 0);
$oferta = sgaSupExigirOferta($ofertaId);
$periodoId = (int)$oferta['periodo_id'];
$grupo = auditoriaGrupo();
try {
    sgaSupValidarCsrf();
    if ($matriculaId <= 0) throw new DomainException('La matrícula seleccionada no es válida.');
    sgaAsegurarPeriodoEditable($periodoId);
    if (!$conexion->begin_transaction()) throw new RuntimeException('No se pudo iniciar la transacción.');
    $stmt = $conexion->prepare("SELECT nf.*,m.estudiante_id,u.apellidos,u.nombres
       FROM notas_finales nf
       JOIN matriculas m ON m.id=nf.matricula_id AND m.estado='activo'
       JOIN usuarios u ON u.id=m.estudiante_id
       WHERE nf.oferta_id=? AND nf.matricula_id=? AND m.aula_periodo_id=? LIMIT 1 FOR UPDATE");
    if (!$stmt) throw new RuntimeException('No se pudo localizar el supletorio.');
    $apId = (int)$oferta['aula_periodo_id'];
    $stmt->bind_param('iii',$ofertaId,$matriculaId,$apId);
    sgaEjecutar($stmt,'verificar el supletorio existente');
    $antes = $stmt->get_result()->fetch_assoc(); $stmt->close();
    if (!$antes || $antes['examen_supletorio']===null) throw new DomainException('No existe una nota de supletorio registrada para este estudiante.');
    $stmt = $conexion->prepare('DELETE FROM notas_finales WHERE oferta_id=? AND matricula_id=?');
    if (!$stmt) throw new RuntimeException('No se pudo preparar la eliminación.');
    $stmt->bind_param('ii',$ofertaId,$matriculaId);
    sgaEjecutar($stmt,'quitar la nota de supletorio');
    $stmt->close();
    sgaAuditoriaObligatoria('DELETE','Calificaciones','nota_supletorio',$ofertaId.'-'.$matriculaId,
        'Supletorio retirado para '.trim($antes['apellidos'].' '.$antes['nombres']).' en '.$oferta['asignatura'].'.',
        (int)$antes['estudiante_id'],['examen_supletorio'=>$antes['examen_supletorio']],null,
        'exito',null,$grupo,'critica');
    if (!$conexion->commit()) throw new RuntimeException('No se pudo confirmar la eliminación.');
    flash('success','Se quitó la nota de supletorio. Los tres trimestres no se modificaron.');
} catch (Throwable $e) {
    try { $conexion->rollback(); } catch (Throwable $ignorado) {}
    error_log('[SGA Supletorios] Error al quitar: '.$e->getMessage());
    flash('error','No se pudo quitar la nota: '.$e->getMessage());
}
redir(sgaSupRetorno($periodoId,$ofertaId));
