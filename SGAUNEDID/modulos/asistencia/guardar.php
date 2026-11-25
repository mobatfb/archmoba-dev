<?php
require_once __DIR__.'/../../lib/funciones.php';
exigirLogin();
if($_SERVER['REQUEST_METHOD']!=='POST') redir('modulos/asistencia/index.php');
$oid=(int)($_POST['oferta_id']??0);$fecha=trim((string)($_POST['fecha']??''));
if(!$oid||!puedeGestionarOferta($oid)){http_response_code(403);die('No tienes acceso a esta asignación.');}
$o=ofertaDetalle($oid);if(!$o){http_response_code(404);die('Asignación inexistente.');}
$destino='modulos/asistencia/registro.php?oferta_id='.$oid.'&fecha='.urlencode($fecha);
$d=DateTime::createFromFormat('!Y-m-d',$fecha);
if(!$d||$d->format('Y-m-d')!==$fecha){flash('error','La fecha de asistencia no es válida.');redir('modulos/asistencia/registro.php?oferta_id='.$oid);}
if((!empty($o['fecha_inicio'])&&$fecha<$o['fecha_inicio'])||(!empty($o['fecha_fin'])&&$fecha>$o['fecha_fin'])){
    flash('error','La fecha está fuera del periodo académico.');redir($destino);
}
$tema=trim((string)($_POST['tema']??''));$observacionesGeneral=trim((string)($_POST['observaciones']??''));
$asistencia=$_POST['asistencia']??null;$observaciones=$_POST['observacion']??[];
$permitidos=['presente','ausente','atraso','justificado'];$uid=(int)$_SESSION['usuario_id'];
$grupo=auditoriaGrupo();$transaccion=false;
$notificarFamilias=!empty($_POST['notificar_representantes']);$avisosFamilia=[];
try{
    sgaAsegurarPeriodoEditable((int)$o['periodo_id']);
    if(!is_array($asistencia)||!is_array($observaciones))throw new DomainException('El formulario de asistencia está incompleto. No se guardó ningún cambio.');
    if(strlen($tema)>255||strlen($observacionesGeneral)>500)throw new DomainException('Las observaciones generales exceden el tamaño permitido.');
    $conexion->begin_transaction();$transaccion=true;
    // Bloquear la lista en el servidor; nunca completar filas ausentes como presentes.
    $s=$conexion->prepare("SELECT m.id,m.estudiante_id,u.apellidos,u.nombres FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id WHERE m.aula_periodo_id=? AND m.estado='activo' ORDER BY m.id FOR UPDATE");
    $apid=(int)$o['aula_periodo_id'];$s->bind_param('i',$apid);sgaEjecutar($s,'consultar las matrículas del aula');
    $matriculas=[];foreach($s->get_result()->fetch_all(MYSQLI_ASSOC) as $r)$matriculas[(int)$r['id']]=$r;$s->close();
    if(!$matriculas)throw new DomainException('El paralelo no tiene estudiantes activos. No se creó la sesión.');
    if(count($asistencia)!==count($matriculas))throw new DomainException('Faltan filas de estudiantes. No se guardó la asistencia para evitar registros incorrectos.');
    $cambios=[];
    foreach($asistencia as $key=>$estado){
        if(!ctype_digit((string)$key)||!isset($matriculas[(int)$key]))throw new DomainException('Se recibió una matrícula ajena al paralelo. No se guardaron cambios.');
        if(!is_string($estado)||!in_array($estado,$permitidos,true))throw new DomainException('Se recibió un estado de asistencia inválido. No se guardaron cambios.');
        $mid=(int)$key;
        $obs=$observaciones[$mid]??'';
        if(!is_string($obs)||strlen($obs)>255)throw new DomainException('La observación del estudiante '.$mid.' no es válida.');
        $cambios[$mid]=['estado'=>$estado,'observacion'=>trim($obs)];
    }
    $s=$conexion->prepare('SELECT id,tema,observaciones,registrado_por FROM asistencia_sesiones WHERE oferta_id=? AND fecha=? LIMIT 1 FOR UPDATE');
    $s->bind_param('is',$oid,$fecha);sgaEjecutar($s,'consultar la sesión');$antesSesion=$s->get_result()->fetch_assoc()?:null;$s->close();
    $s=$conexion->prepare("INSERT INTO asistencia_sesiones(oferta_id,fecha,tema,observaciones,registrado_por)
         VALUES(?,?,?,?,?) ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id),tema=VALUES(tema),observaciones=VALUES(observaciones),registrado_por=VALUES(registrado_por),actualizado_en=CURRENT_TIMESTAMP");
    $s->bind_param('isssi',$oid,$fecha,$tema,$observacionesGeneral,$uid);sgaEjecutar($s,'guardar la sesión de asistencia');$sid=(int)$conexion->insert_id;$s->close();
    if(!$sid){$s=$conexion->prepare('SELECT id FROM asistencia_sesiones WHERE oferta_id=? AND fecha=?');$s->bind_param('is',$oid,$fecha);sgaEjecutar($s,'recuperar sesión');$sid=(int)($s->get_result()->fetch_assoc()['id']??0);$s->close();}
    if(!$sid)throw new RuntimeException('No se pudo identificar la sesión de asistencia.');
    // Todas las observaciones anteriores se recuperan en una consulta, no una por estudiante.
    $s=$conexion->prepare('SELECT matricula_id,estado,observacion FROM asistencia_detalle WHERE sesion_id=?');
    $s->bind_param('i',$sid);sgaEjecutar($s,'consultar las asistencias anteriores');
    $anteriores=[];foreach($s->get_result()->fetch_all(MYSQLI_ASSOC) as $r)$anteriores[(int)$r['matricula_id']]=['estado'=>$r['estado'],'observacion'=>$r['observacion']];$s->close();
    $up=$conexion->prepare("INSERT INTO asistencia_detalle(sesion_id,matricula_id,estado,observacion) VALUES(?,?,?,?)
         ON DUPLICATE KEY UPDATE estado=VALUES(estado),observacion=VALUES(observacion),actualizado_en=CURRENT_TIMESTAMP");
    foreach($cambios as $mid=>$nuevo){
        $estado=$nuevo['estado'];$obs=$nuevo['observacion'];
        $up->bind_param('iiss',$sid,$mid,$estado,$obs);sgaEjecutar($up,'guardar asistencia de matrícula '.$mid);
        $antes=$anteriores[$mid]??null;
        if($antes!==$nuevo){
            $mat=$matriculas[$mid];
            if($notificarFamilias && in_array($estado,['ausente','atraso'],true)
                && (!$antes || ($antes['estado']??'')!==$estado)) {
                $avisosFamilia[]=['estudiante_id'=>(int)$mat['estudiante_id'],'matricula_id'=>$mid,'estado'=>$estado];
            }
            sgaAuditoriaObligatoria($antes?'UPDATE':'CREATE','Asistencia','asistencia_detalle',$sid.'-'.$mid,
               'Asistencia de '.$mat['apellidos'].' '.$mat['nombres'].' registrada como '.$estado.' en '.$o['asignatura'].' · '.$fecha.'.',
               (int)$mat['estudiante_id'],$antes,$nuevo,'exito',null,$grupo,$estado==='ausente'?'advertencia':'info');
        }
    }
    $up->close();
    sgaAuditoriaObligatoria($antesSesion?'UPDATE':'CREATE','Asistencia','asistencia_sesion',$sid,
        ($antesSesion?'Asistencia actualizada':'Asistencia registrada').' · '.$o['asignatura'].' · '.$fecha.'.',
        null,$antesSesion,['oferta_id'=>$oid,'fecha'=>$fecha,'tema'=>$tema,'observaciones'=>$observacionesGeneral,'registrado_por'=>$uid],
        'exito',null,$grupo,'info');
    if(!$conexion->commit())throw new RuntimeException('No se pudo confirmar la sesión de asistencia.');
    $transaccion=false;
    $avisosProgramados=0;
    if($avisosFamilia){
        try{
            require_once __DIR__.'/../../lib/sga_representantes.php';
            foreach($avisosFamilia as $av){
                $estudiante=(int)$av['estudiante_id'];
                if(!sgaRepRepresentantesDe($estudiante))continue;
                $estadoAviso=$av['estado'];
                $descripcion= $estadoAviso==='ausente'?'una ausencia':'un atraso';
                $asunto='Registro de '.$descripcion.' · '.$fecha;
                $detalle='Se ha registrado '.$descripcion.' en la asignatura '.$o['asignatura'].' el '.$fecha.'. Para más información, comunícate con la institución.';
                $claveEvento='asistencia:'.$sid.':'.(int)$av['matricula_id'].':'.$estadoAviso;
                sgaRepCrearNovedad($estudiante,(int)$o['periodo_id'],$uid,'asistencia',$asunto,$detalle,$claveEvento);
                $avisosProgramados++;
            }
            // Entregar unas pocas notificaciones inmediatamente; el cron completa la cola.
            if($avisosProgramados>0)sgaRepEnviarPendientes(4);
        }catch(Throwable $errorFamilias){
            error_log('[SGA UNEDID] La asistencia se guardo pero hubo un problema de notificacion: '.get_class($errorFamilias));
        }
    }
    flash('success',($antesSesion?'Asistencia actualizada':'Asistencia guardada').' correctamente para '.count($cambios).' estudiantes.'
        .($avisosProgramados>0?' Se programaron alertas familiares para '.$avisosProgramados.' estudiante(s).':''));
}catch(Throwable $e){
    if($transaccion)try{$conexion->rollback();}catch(Throwable $ignorada){}
    registrarAuditoria('UPDATE','Asistencia','asistencia_sesion',$oid.'-'.$fecha,'Falló el guardado de asistencia: '.$e->getMessage(),null,null,['fecha'=>$fecha],'fallo',null,$grupo,'critica');
    flash('error','No se guardó la asistencia: '.$e->getMessage());
}
redir($destino);
