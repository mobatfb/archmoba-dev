<?php
require_once __DIR__.'/../../lib/funciones.php';exigirLogin();$oid=(int)($_POST['oferta_id']??0);$trim=(int)($_POST['trimestre']??0);$campo=(string)($_POST['campo']??'');$activo=(int)($_POST['activo']??0)===1?1:0;$permitidos=['deber_ap1','deber_ap2','deber_ap3','tarea_ap1','tarea_ap2','tarea_ap3','leccion_ap1','leccion_ap2','leccion_ap3','grupo_ap1','grupo_ap2','grupo_ap3'];if(!$oid||$trim<1||$trim>3||!in_array($campo,$permitidos,true)||!puedeGestionarOferta($oid)){http_response_code(403);die('Operación no permitida.');}impedirNotasEnVisorComportamiento($oid);$o=ofertaDetalle($oid);$antesEstado=obtenerEstadoAportes($oid,$trim);
try{sgaAsegurarPeriodoEditable((int)$o['periodo_id']);$conexion->begin_transaction();$stmt=$conexion->prepare('INSERT INTO configuracion_aportes(oferta_id,trimestre,campo,activo) VALUES(?,?,?,?) ON DUPLICATE KEY UPDATE activo=VALUES(activo)');$stmt->bind_param('iisi',$oid,$trim,$campo,$activo);$stmt->execute();$stmt->close();
// Inicializa el campo en 0 en registros ya existentes.
$sql="UPDATE calificaciones_trimestre SET `$campo`=0.00 WHERE oferta_id=? AND trimestre=?";$stmt=$conexion->prepare($sql);$stmt->bind_param('ii',$oid,$trim);$stmt->execute();$stmt->close();
// Recalcula todos los registros existentes con los nuevos campos sumativos.
$estado=obtenerEstadoAportes($oid,$trim);
$config=obtenerConfiguracion((int)$o['periodo_id']);
$recalcular=['deber_promedio','deber_promedio_aporte','tarea_promedio','tarea_promedio_aporte',
    'leccion_promedio','leccion_promedio_aporte','grupo_promedio','grupo_promedio_aporte',
    'promedio_aportes','ponderado_aportes','promedio_disciplinar','promedio_proyecto',
    'promedio_evaluacion_sumativa','ponderado_sumativa','nota_final','cualitativo'];
$sqlRec='UPDATE calificaciones_trimestre SET '.implode(',',array_map(static fn($c)=>'`'.$c.'`=?',$recalcular)).' WHERE id=?';
$stmtRec=$conexion->prepare($sqlRec);
$res=$conexion->query("SELECT * FROM calificaciones_trimestre WHERE oferta_id=$oid AND trimestre=$trim");
while($r=$res->fetch_assoc()){
    $n=[];
    foreach(['deber_ap1','deber_ap2','deber_ap3','deber_refuerzo',
        'tarea_ap1','tarea_ap2','tarea_ap3','tarea_refuerzo',
        'leccion_ap1','leccion_ap2','leccion_ap3','leccion_refuerzo',
        'grupo_ap1','grupo_ap2','grupo_ap3','grupo_refuerzo',
        'nota_disciplinar','trabajo_refuerzo_disciplinar','nota_producto_final',
        'proyecto_interdisciplinar','proyecto_refuerzo','actividad_mejora',
        'promedio_proyecto','ponderado_sumativa'] as $c)
        $n[$c]=$r[$c]===null?null:(float)$r[$c];
    $calc=calcularTrimestre($n,$config,$o['asignatura'],(bool)$o['usa_literal_especial'],$estado,!empty($o['aula_resultados_cualitativos']));
    $valores=[];foreach($recalcular as $c)$valores[]=$calc[$c];
    $valores[]=(int)$r['id'];
    $refs=[];foreach($valores as $k=>&$v)$refs[$k]=&$v;unset($v);
    array_unshift($refs,str_repeat('d',count($recalcular)-1).'si');
    call_user_func_array([$stmtRec,'bind_param'],$refs);
    $stmtRec->execute();
}
$stmtRec->close();
$despuesEstado=obtenerEstadoAportes($oid,$trim);sgaAuditoriaObligatoria('UPDATE','Calificaciones','configuracion_aporte',$oid.'-'.$trim.'-'.$campo,($activo?'Aporte habilitado':'Aporte bloqueado').' en '.$o['asignatura'].' · trimestre '.$trim.'.',null,['campo'=>$campo,'activo'=>$antesEstado[$campo]??true],['campo'=>$campo,'activo'=>(bool)$activo],'exito',null,null,'advertencia');if(!$conexion->commit())throw new RuntimeException('No se pudo confirmar el aporte.');flash('success',$activo?'Aporte habilitado. Los vacíos activos se consideran 0,00.':'Aporte bloqueado como no utilizado.');}catch(Throwable $e){$conexion->rollback();flash('error',$e->getMessage());}redir('modulos/calificaciones/index.php?oferta_id='.$oid.'&trimestre='.$trim);
