<?php
/**
 * Traslado trazable: conserva notas y asistencias vinculadas a la matricula original.
 * La matricula anterior queda RETIRADA; se crea/reactiva otra en el aula destino.
 */
require_once __DIR__.'/funciones.php';
function sgaTrasladarMatricula(int $mid, int $origen, int $destino, int $periodoId): array {
    global $conexion;
    if($mid<=0||$origen<=0||$destino<=0||$origen===$destino)
        throw new DomainException('Selecciona un paralelo diferente para realizar el traslado.');
    if(!esAdminAcademico())throw new DomainException('Los traslados requieren administración académica.');
    exigirAccesoAulaPeriodo($origen);exigirAccesoAulaPeriodo($destino);
    sgaAsegurarPeriodoEditable($periodoId);
    $conexion->begin_transaction();
    try {
        $s=$conexion->prepare("SELECT m.*,ap.periodo_id,u.apellidos,u.nombres
          FROM matriculas m JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id
          JOIN usuarios u ON u.id=m.estudiante_id
          WHERE m.id=? AND m.aula_periodo_id=? LIMIT 1 FOR UPDATE");
        $s->bind_param('ii',$mid,$origen);sgaEjecutar($s,'consultar la matricula de origen');
        $anterior=$s->get_result()->fetch_assoc();$s->close();
        if(!$anterior||$anterior['estado']!=='activo'||(int)$anterior['periodo_id']!==$periodoId)
            throw new DomainException('La matricula de origen no está activa en este periodo.');
        $s=$conexion->prepare('SELECT ap.id FROM aulas_periodo ap WHERE ap.id=? AND ap.periodo_id=? AND ap.activo=1 FOR UPDATE');
        $s->bind_param('ii',$destino,$periodoId);sgaEjecutar($s,'validar el aula de destino');
        $destinoExiste=$s->get_result()->fetch_assoc();$s->close();
        if(!$destinoExiste)throw new DomainException('El paralelo de destino no está habilitado para este periodo.');
        $s=$conexion->prepare("UPDATE matriculas SET estado='retirado' WHERE id=? AND aula_periodo_id=? AND estado='activo'");
        $s->bind_param('ii',$mid,$origen);sgaEjecutar($s,'retirar la matricula anterior');
        if($s->affected_rows!==1)throw new RuntimeException('La matricula cambió durante el traslado.');$s->close();
        $uid=(int)$anterior['estudiante_id'];
        $resultado=matricularUsuarioEnAula($uid,$destino,$periodoId);
        if(!in_array($resultado['estado'],['creado','reactivado'],true))
            throw new DomainException($resultado['mensaje']??'No se pudo matricular en el aula de destino.');
        $destinoMid=(int)$resultado['matricula_id'];$grupo=auditoriaGrupo();
        sgaAuditoriaObligatoria('UPDATE','Matrículas','matricula',$mid,
           'Traslado: matricula anterior retirada, historial preservado.', $uid,
           ['estado'=>'activo','aula_periodo_id'=>$origen],['estado'=>'retirado','aula_periodo_id'=>$origen,'destino_matricula_id'=>$destinoMid],
           'exito',null,$grupo,'advertencia');
        sgaAuditoriaObligatoria($resultado['estado']==='creado'?'CREATE':'UPDATE','Matrículas','matricula',$destinoMid,
           'Traslado: matrícula de destino asignada.', $uid,
           null,['estado'=>'activo','aula_periodo_id'=>$destino,'origen_matricula_id'=>$mid],
           'exito',null,$grupo,'advertencia');
        if(!$conexion->commit())throw new RuntimeException('No se pudo confirmar el traslado.');
        return ['estudiante'=>trim($anterior['apellidos'].' '.$anterior['nombres']),
           'matricula_origen'=>$mid,'matricula_destino'=>$destinoMid];
    }catch(Throwable $e){try{$conexion->rollback();}catch(Throwable $ignorado){}throw $e;}
}
