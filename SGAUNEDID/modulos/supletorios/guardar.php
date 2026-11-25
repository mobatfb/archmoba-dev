<?php
/** Registro individual con control de rol, matrícula, trimestre, CSRF y auditoría. */
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
    if ($matriculaId <= 0) throw new DomainException('Selecciona una matrícula válida.');
    if (!isset($_POST['nota']) || !is_scalar($_POST['nota'])) throw new DomainException('Ingresa una calificación válida.');
    $valor = trim((string)$_POST['nota']);
    // No convertir cadenas inválidas en null ni redondear más de dos decimales.
    if (!preg_match('/^(?:10(?:[.,]0{1,2})?|[0-9](?:[.,][0-9]{1,2})?)$/D', $valor)) {
        throw new DomainException('La nota debe tener entre 0.01 y 10.00, con máximo dos decimales.');
    }
    $nota = notaEntrada($valor);
    if ($nota === null) throw new DomainException('La nota del examen es obligatoria.');
    sgaAsegurarPeriodoEditable($periodoId);
    if (!$conexion->begin_transaction()) throw new RuntimeException('No se pudo iniciar la transacción.');
    $s = $conexion->prepare("SELECT m.id,m.estudiante_id,u.apellidos,u.nombres,
        ct1.nota_final t1,ct2.nota_final t2,ct3.nota_final t3,nf.examen_supletorio anterior
      FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id
      LEFT JOIN calificaciones_trimestre ct1 ON ct1.matricula_id=m.id AND ct1.oferta_id=? AND ct1.trimestre=1
      LEFT JOIN calificaciones_trimestre ct2 ON ct2.matricula_id=m.id AND ct2.oferta_id=? AND ct2.trimestre=2
      LEFT JOIN calificaciones_trimestre ct3 ON ct3.matricula_id=m.id AND ct3.oferta_id=? AND ct3.trimestre=3
      LEFT JOIN notas_finales nf ON nf.matricula_id=m.id AND nf.oferta_id=?
      WHERE m.id=? AND m.aula_periodo_id=? AND m.estado='activo'
      LIMIT 1 FOR UPDATE");
    if (!$s) throw new RuntimeException('No se pudo verificar la matrícula.');
    $apId = (int)$oferta['aula_periodo_id'];
    $s->bind_param('iiiiii',$ofertaId,$ofertaId,$ofertaId,$ofertaId,$matriculaId,$apId);
    sgaEjecutar($s,'consultar la matrícula y los trimestres');
    $fila = $s->get_result()->fetch_assoc();
    $s->close();
    if (!$fila) throw new DomainException('El estudiante no está matriculado activamente en esta asignatura.');
    $config = obtenerConfiguracion($periodoId);
    sgaValidarSupletorio(
        $fila['t1']===null?null:(float)$fila['t1'],
        $fila['t2']===null?null:(float)$fila['t2'],
        $fila['t3']===null?null:(float)$fila['t3'],
        $nota, $config
    );
    $anterior = $fila['anterior']===null ? null : (float)$fila['anterior'];
    if ($anterior !== null && abs($anterior-$nota) < 0.00001) {
        $conexion->rollback();
        flash('success','La nota ya estaba registrada; no se realizó ningún cambio.');
        redir(sgaSupRetorno($periodoId,$ofertaId));
    }
    $save = $conexion->prepare('INSERT INTO notas_finales(oferta_id,matricula_id,examen_supletorio) VALUES(?,?,?) ON DUPLICATE KEY UPDATE examen_supletorio=VALUES(examen_supletorio)');
    if (!$save) throw new RuntimeException('No se pudo preparar el registro de la nota.');
    $save->bind_param('iid',$ofertaId,$matriculaId,$nota);
    sgaEjecutar($save,'guardar supletorio');
    $save->close();
    $esNuevo = $anterior === null;
    sgaAuditoriaObligatoria($esNuevo?'CREATE':'UPDATE','Calificaciones','nota_supletorio',$ofertaId.'-'.$matriculaId,
        'Nota de supletorio registrada desde el módulo Supletorios para '.trim($fila['apellidos'].' '.$fila['nombres']).' en '.$oferta['asignatura'].'.',
        (int)$fila['estudiante_id'], ['examen_supletorio'=>$anterior], ['examen_supletorio'=>$nota],
        'exito',null,$grupo,'advertencia');
    if (!$conexion->commit()) throw new RuntimeException('No se pudo confirmar la calificación.');
    flash('success',$esNuevo?'Supletorio registrado. El consolidado final se actualizó.':'Nota de supletorio actualizada correctamente.');
} catch (Throwable $e) {
    try { $conexion->rollback(); } catch (Throwable $ignorado) {}
    error_log('[SGA Supletorios] Error al guardar: '. $e->getMessage());
    flash('error','No se pudo guardar la nota: '.$e->getMessage());
}
redir(sgaSupRetorno($periodoId,$ofertaId));
