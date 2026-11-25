<?php
require_once __DIR__.'/../../lib/funciones.php';
exigirLogin();
$oid=(int)($_POST['oferta_id']??0);
$trim=(int)($_POST['trimestre']??0);
if(!$oid||$trim<1||$trim>3||!puedeGestionarOferta($oid)){http_response_code(403);die('Operación no permitida.');}
if (empty($_SESSION['csrf_calificaciones']) || !hash_equals($_SESSION['csrf_calificaciones'],(string)($_POST['csrf']??''))) {
    http_response_code(403);die('Solicitud inválida. Recarga la página de calificaciones.');
}
impedirNotasEnVisorComportamiento($oid);$o=ofertaDetalle($oid);
if(!$o){http_response_code(404);die('Asignatura inexistente.');}
try{sgaAsegurarPeriodoEditable((int)$o['periodo_id']);}catch(Throwable $e){flash('error',$e->getMessage());redir('modulos/calificaciones/index.php?oferta_id='.$oid.'&trimestre='.$trim);}
$config=obtenerConfiguracion((int)$o['periodo_id']);
$estado=obtenerEstadoAportes($oid,$trim);
$notas=$_POST['notas']??[];
if (!is_array($notas)) { http_response_code(400);die('Formato de notas inválido.'); }
$soloFila=isset($_POST['guardar_matricula_id']) ? (int)$_POST['guardar_matricula_id'] : 0;
if (isset($_POST['guardar_matricula_id'])) {
    if ($soloFila<=0 || !isset($notas[$soloFila]) || !is_array($notas[$soloFila])) {
        flash('error','No se recibió la fila seleccionada. Actualiza la página y vuelve a guardar.');
        redir('modulos/calificaciones/index.php?oferta_id='.$oid.'&trimestre='.$trim);
    }
    $notas=[$soloFila=>$notas[$soloFila]];
}
$raw=['deber_ap1','deber_ap2','deber_ap3','deber_refuerzo','tarea_ap1','tarea_ap2','tarea_ap3','tarea_refuerzo','leccion_ap1','leccion_ap2','leccion_ap3','leccion_refuerzo','grupo_ap1','grupo_ap2','grupo_ap3','grupo_refuerzo','nota_disciplinar','trabajo_refuerzo_disciplinar','nota_producto_final'];
// Evita guardar filas incompletas si el hosting limita max_input_vars o la solicitud se trunca.
$requeridos=array_values(array_filter($raw,static function($campo)use($estado){
    return !preg_match('/^(deber|tarea|leccion|grupo)_ap[123]$/',$campo) || aporteActivo($estado,$campo);
}));
foreach ($notas as $filasRecibidas) {
    if (!is_array($filasRecibidas) || array_diff($requeridos,array_keys($filasRecibidas))) {
        flash('error','El formulario llegó incompleto. Las notas no se modificaron. Usa Guardar por fila o solicita aumentar max_input_vars en el hosting.');
        redir('modulos/calificaciones/index.php?oferta_id='.$oid.'&trimestre='.$trim);
    }
}
if ($soloFila===0) {
    $apidRevision=(int)$o['aula_periodo_id'];
    $stmtRevision=$conexion->prepare("SELECT COUNT(*) total FROM matriculas WHERE aula_periodo_id=? AND estado='activo'");
    $stmtRevision->bind_param('i',$apidRevision);$stmtRevision->execute();
    $esperadas=(int)$stmtRevision->get_result()->fetch_assoc()['total'];$stmtRevision->close();
    if (count($notas)!==$esperadas) {
        flash('error','No se recibieron todas las filas del paralelo. No se guardó ninguna nota. Usa el botón Guardar de cada fila o amplía max_input_vars del servidor.');
        redir('modulos/calificaciones/index.php?oferta_id='.$oid.'&trimestre='.$trim);
    }
}

if(!$notas){
    registrarAuditoria('UPDATE','Calificaciones','oferta_academica',$oid,'Intento de guardar calificaciones sin datos recibidos.',null,null,['trimestre'=>$trim],'fallo',null,null,'advertencia');
    flash('error','No se recibieron calificaciones para guardar. Recarga la página e inténtalo nuevamente.');
    redir('modulos/calificaciones/index.php?oferta_id='.$oid.'&trimestre='.$trim);
}
// No sobrescribir las columnas históricas (proyecto_interdisciplinar / proyecto_refuerzo / actividad_mejora).
$persistir=[
    'deber_ap1','deber_ap2','deber_ap3','deber_promedio','deber_refuerzo','deber_promedio_aporte',
    'tarea_ap1','tarea_ap2','tarea_ap3','tarea_promedio','tarea_refuerzo','tarea_promedio_aporte',
    'leccion_ap1','leccion_ap2','leccion_ap3','leccion_promedio','leccion_refuerzo','leccion_promedio_aporte',
    'grupo_ap1','grupo_ap2','grupo_ap3','grupo_promedio','grupo_refuerzo','grupo_promedio_aporte',
    'promedio_aportes','ponderado_aportes',
    'nota_disciplinar','trabajo_refuerzo_disciplinar','promedio_disciplinar','nota_producto_final',
    'promedio_proyecto','promedio_evaluacion_sumativa','ponderado_sumativa','nota_final','cualitativo'
];
$columnas=array_merge(['oferta_id','matricula_id','trimestre'],$persistir);
$sql='INSERT INTO calificaciones_trimestre (`'.implode('`,`',$columnas).'`) VALUES ('.implode(',',array_fill(0,count($columnas),'?')).') ON DUPLICATE KEY UPDATE '.implode(',',array_map(static fn($c)=>'`'.$c.'`=VALUES(`'.$c.'`)',$persistir));
$guardados=0;$save=null;$audits=[];$grupoAud=auditoriaGrupo();
try{
    $save=$conexion->prepare($sql);
    if(!$save)throw new RuntimeException('No se pudo preparar el guardado de calificaciones: '.$conexion->error);
    $conexion->begin_transaction();
    foreach($notas as $midRaw=>$entrada){
        $mid=(int)$midRaw;if(!$mid||!is_array($entrada))continue;
        $apid=(int)$o['aula_periodo_id'];
        $check=$conexion->prepare("SELECT m.id,m.estudiante_id,u.cedula,u.apellidos,u.nombres FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id WHERE m.id=? AND m.aula_periodo_id=? AND m.estado='activo' LIMIT 1");
        $check->bind_param('ii',$mid,$apid);$check->execute();$mat=$check->get_result()->fetch_assoc();$check->close();if(!$mat)continue;
        $old=$conexion->prepare('SELECT * FROM calificaciones_trimestre WHERE oferta_id=? AND matricula_id=? AND trimestre=? LIMIT 1');
        $old->bind_param('iii',$oid,$mid,$trim);$old->execute();$antes=$old->get_result()->fetch_assoc()?:null;$old->close();
        if($antes){unset($antes['id'],$antes['oferta_id'],$antes['matricula_id'],$antes['trimestre'],$antes['actualizado_en']);}
        $n=[];foreach($raw as $c)$n[$c]=notaEntrada($entrada[$c]??null);
        foreach($estado as $c=>$activo){if(!$activo||$n[$c]===null)$n[$c]=0.0;}
        // Se suministran los antiguos resultados solo para preservarlos si no se ingresaron nuevas notas.
        foreach(['proyecto_interdisciplinar','proyecto_refuerzo','actividad_mejora','promedio_proyecto','ponderado_sumativa'] as $c)
            $n[$c]=$antes&&$antes[$c]!==null?(float)$antes[$c]:null;
        $calc=calcularTrimestre($n,$config,$o['asignatura'],(bool)$o['usa_literal_especial'],$estado,!empty($o['aula_resultados_cualitativos']));
        $valores=array_merge($n,$calc);
        $params=[$oid,$mid,$trim];
        foreach($persistir as $campoPersistente)$params[]=$valores[$campoPersistente];
        $types='iii'.str_repeat('d',count($persistir)-1).'s';
        $refs=[];
        foreach($params as $k=>&$valorParam)$refs[$k]=&$valorParam;
        unset($valorParam);
        array_unshift($refs,$types);
        call_user_func_array([$save,'bind_param'],$refs);
        if(!$save->execute())throw new RuntimeException('No se pudo guardar la matrícula '.$mid.': '.$save->error);
        $despues=array_merge($n,$calc,['trimestre'=>$trim,'asignatura'=>$o['asignatura']]);
        $audits[]=['uid'=>(int)$mat['estudiante_id'],'mid'=>$mid,'nombre'=>$mat['apellidos'].' '.$mat['nombres'],'antes'=>$antes,'despues'=>$despues];
        $guardados++;
    }
    foreach($audits as $a){
        sgaAuditoriaObligatoria($a['antes']?'UPDATE':'CREATE','Calificaciones','calificacion_trimestre',$oid.'-'.$a['mid'].'-'.$trim,'Calificaciones de '.$a['nombre'].' guardadas en '.$o['asignatura'].' · trimestre '.$trim.'.',$a['uid'],$a['antes'],$a['despues'],'exito',null,$grupoAud,'advertencia');
    }
    sgaAuditoriaObligatoria('UPDATE','Calificaciones','oferta_academica',$oid,"Guardado masivo de calificaciones: $guardados estudiantes · {$o['asignatura']} · trimestre $trim.",null,null,['trimestre'=>$trim,'estudiantes'=>$guardados,'asignatura'=>$o['asignatura']],'exito',null,$grupoAud,'info');
    if(!$conexion->commit())throw new RuntimeException('No se pudieron confirmar los cambios de calificaciones.');
    flash('success', $soloFila>0 ? 'Se guardaron y recalcularon las notas del estudiante.' : "Se guardaron y recalcularon $guardados estudiantes.");
}catch(Throwable $e){
    try{$conexion->rollback();}catch(Throwable $rollbackError){}
    registrarAuditoria('UPDATE','Calificaciones','oferta_academica',$oid,'Falló el guardado de calificaciones: '.$e->getMessage(),null,null,['trimestre'=>$trim],'fallo',null,$grupoAud,'critica');
    flash('error',$e->getMessage());
}
if($save instanceof mysqli_stmt)$save->close();
redir('modulos/calificaciones/index.php?oferta_id='.$oid.'&trimestre='.$trim);
