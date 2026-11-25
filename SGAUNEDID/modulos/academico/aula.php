<?php
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/traslado_matricula.php';
require_once __DIR__.'/../../lib/sga_asignaturas_jornadas.php';
exigirAdminAcademico();
$apId=(int)($_GET['id']??$_POST['aula_periodo_id']??0);
exigirAccesoAulaPeriodo($apId);
if(!sgaAreasJornadasInstaladas($conexion) || !sgaAsignaturasJornadasInstaladas($conexion)) {
  http_response_code(503);
  die('Configuración pendiente: instala SQL_SGA_ASIGNATURAS_MULTI_JORNADA.sql antes de gestionar asignaturas de esta aula.');
}
/**
 * Los docentes disponibles para el subadministrador deben tener asignada
 * la jornada DEL AULA para este periodo (usuarios_jornadas_gestion).
 * Docentes con varias jornadas pueden aparecer en cada una de ellas.
 * El administrador principal conserva el catalogo completo.
 */
function sgaFiltroDocentesDisponiblesEnAula(int $periodoId, int $jornadaId): string {
    // Solo docentes del PERIODO. La funcion docente puede coexistir con
    // un rol administrativo; elegir a alguien no modifica su rol global.
    $p=(int)$periodoId;
    $filtro = "u.activo=1 AND EXISTS ("
        ."SELECT 1 FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id "
        ."WHERE ur.usuario_id=u.id AND r.codigo='docente' AND ur.periodo_id={$p}"
        .")";
    if (esSubadmin() && !esSuperadmin()) {
        // Una asignacion docente es una gestion academica, NO de roles.
        // Admitir al colega de la misma jornada aunque tambien sea subadmin.
        // La jornada sale del aula autorizada, nunca del formulario recibido.
        if ($periodoId <= 0 || $jornadaId <= 0 || !puedeAccederJornada($jornadaId,$periodoId)) {
            $filtro .= ' AND 1=0';
        } else {
            $filtro .= ' AND '.sgaUsuarioVisibleEnJornadasSQL($periodoId,[$jornadaId],'u');
        }
    }
    return $filtro;
}
/** Valida en POST exactamente el mismo catalogo que se ofrece en pantalla. */
function sgaExigirDocenteDisponibleEnAula(int $docenteId, int $periodoId, int $jornadaId): void {
    global $conexion;
    if ($docenteId <= 0) throw new RuntimeException('Selecciona un docente válido.');
    $sql = 'SELECT 1 FROM usuarios u WHERE u.id=? AND '.sgaFiltroDocentesDisponiblesEnAula($periodoId, $jornadaId).' LIMIT 1';
    $stmt = $conexion->prepare($sql);
    if (!$stmt) throw new RuntimeException('No se pudo validar al docente.');
    $stmt->bind_param('i', $docenteId);
    if (!$stmt->execute()) {
        $stmt->close();
        throw new RuntimeException('No se pudo comprobar la jornada del docente.');
    }
    $valido = (bool)$stmt->get_result()->fetch_row();
    $stmt->close();
    if (!$valido) throw new RuntimeException('El docente no esta disponible para la jornada de esta aula.');
}
$stmt=$conexion->prepare('SELECT ap.*,p.nombre periodo,a.nivel,a.nombre aula,a.paralelo,a.jornada_id,j.nombre jornada FROM aulas_periodo ap JOIN periodos_academicos p ON p.id=ap.periodo_id JOIN aulas a ON a.id=ap.aula_id LEFT JOIN jornadas j ON j.id=a.jornada_id WHERE ap.id=? LIMIT 1');$stmt->bind_param('i',$apId);$stmt->execute();$ap=$stmt->get_result()->fetch_assoc();$stmt->close();if(!$ap)die('Aula del periodo no encontrada.');$pid=(int)$ap['periodo_id'];$jornadaAulaId=(int)($ap['jornada_id']??0);
$modoParametros=!empty($ap['evaluacion_cualitativa_parametros']);
// Token CSRF exclusivo para ordenar listados desde esta pantalla.
if (empty($_SESSION['csrf_aula_gestion'])) $_SESSION['csrf_aula_gestion']=bin2hex(random_bytes(24));
$csrfAulaGestion=(string)$_SESSION['csrf_aula_gestion'];
if (empty($_SESSION['csrf_reordenar_aula'])) {
    $_SESSION['csrf_reordenar_aula'] = bin2hex(random_bytes(32));
}


if($_SERVER['REQUEST_METHOD']==='POST'){
  $accion=(string)($_POST['accion']??'');
  $sgaTransaccionSimple=false;
  try{
    if(!hash_equals($csrfAulaGestion,(string)($_POST['csrf_aula_gestion']??'')))
        throw new RuntimeException('Formulario de aula caducado. Recarga la página.');
    sgaAsegurarPeriodoEditable($pid);
    if(in_array($accion,['oferta','editar_oferta','toggle_oferta','eliminar_oferta','guardar_asignaturas','guardar_docentes','oferta_individual','asignar_docente_aula','retirar','editar_matricula','eliminar_matricula','reordenar_alfabeticamente'],true)){
      if(!$conexion->begin_transaction())throw new RuntimeException('No se pudo iniciar la transaccion academica.');
      $sgaTransaccionSimple=true;
    }
    $accionesOferta=['oferta','editar_oferta','toggle_oferta','eliminar_oferta','guardar_asignaturas','guardar_docentes','oferta_individual'];
    if(in_array($accion,array_merge($accionesOferta,['asignar_docente_aula']),true)){
      $actualAula=sgaParametrosBloquearAula($conexion,$apId);
      $modoParametros=!empty($actualAula['evaluacion_cualitativa_parametros']);
      if(!$modoParametros && in_array($accion,$accionesOferta,true)){
        $q=$conexion->prepare('SELECT asignatura_id FROM ofertas_academicas WHERE aula_periodo_id=? AND (evaluacion_aula=1 OR evaluacion_parametros_historica=1)');$q->bind_param('i',$apId);sgaEjecutar($q,'verificar historial cualitativo');$asigHist=array_map('intval',array_column($q->get_result()->fetch_all(MYSQLI_ASSOC),'asignatura_id'));$q->close();
        $idsPost=[(int)($_POST['asignatura_id']??0)];foreach(['asignaturas','asignaturas_docente'] as $campo){if(is_array($_POST[$campo]??null))foreach($_POST[$campo] as $v)if(is_scalar($v))$idsPost[]=(int)$v;}
        if(array_intersect($asigHist,$idsPost))throw new RuntimeException('La asignatura conserva el registro histórico de evaluación cualitativa de esta aula.');
      }
      if($modoParametros && in_array($accion,$accionesOferta,true))throw new RuntimeException('Esta aula se evalúa por parámetros; asigna solamente su docente responsable.');
      if(!$modoParametros && $accion==='asignar_docente_aula')throw new RuntimeException('Activa primero la evaluación por parámetros en Aulas.');
      if(!$modoParametros && in_array($accion,['editar_oferta','toggle_oferta','eliminar_oferta'],true)){
        $oidPost=(int)($_POST['oferta_id']??0);
        foreach(sgaParametrosOfertasAula($conexion,$apId) as $of)if((int)$of['id']===$oidPost)throw new RuntimeException('El registro de evaluación cualitativa pertenece al historial del aula.');
      }
    }
    if($accion==='asignar_docente_aula'){
      $doc=(int)($_POST['docente_id']??0);sgaExigirDocenteDisponibleEnAula($doc,$pid,$jornadaAulaId);
      sgaParametrosAsignarDocenteAula($conexion,$apId,$doc,(int)($_POST['origen_id']??0));
      flash('success','Docente único del aula guardado. Puede registrar los tres trimestres.');
    }elseif($accion==='matricular'){
      $ids=array_values(array_unique(array_filter(array_map('intval',$_POST['usuarios']??[]))));if(!$ids)throw new Exception('Selecciona al menos un usuario.');$conexion->begin_transaction();$creados=$reactivados=$existentes=$conflictos=0;$mensajes=[];$audMat=[];$grupoAud=auditoriaGrupo();foreach($ids as $uid){$r=matricularUsuarioEnAula($uid,$apId,$pid);if($r['estado']==='creado'){$creados++;$audMat[]=['accion'=>'CREATE','uid'=>$uid,'mid'=>$r['matricula_id']??null,'detalle'=>'Estudiante matriculado manualmente.'];}elseif($r['estado']==='reactivado'){$reactivados++;$audMat[]=['accion'=>'UPDATE','uid'=>$uid,'mid'=>$r['matricula_id']??null,'detalle'=>'Matrícula reactivada manualmente.'];}elseif($r['estado']==='existente')$existentes++;elseif($r['estado']==='conflicto'){$conflictos++;$mensajes[]=$r['mensaje'];}}foreach($audMat as $a)sgaAuditoriaObligatoria($a['accion'],'Matrículas','matricula',$a['mid'],$a['detalle'],$a['uid'],null,['aula_periodo_id'=>$apId,'periodo_id'=>$pid,'estado'=>'activo'],'exito',null,$grupoAud,'info');if(!$conexion->commit())throw new RuntimeException('No se pudieron confirmar las matriculas.');$msg="Proceso terminado: $creados nuevas, $reactivados reactivadas, $existentes ya existentes".($conflictos?", $conflictos con conflicto":'').'.';if($mensajes)$msg.=' '.implode(' ',array_slice(array_unique($mensajes),0,3));flash($conflictos?'info':'success',$msg);
    }elseif($accion==='trasladar'){
      $traslado=sgaTrasladarMatricula((int)($_POST['matricula_id']??0),$apId,(int)($_POST['destino_apid']??0),$pid);
      flash('success','Traslado completado para '.$traslado['estudiante'].'. Notas y asistencias anteriores conservadas en el paralelo de origen.');
    }elseif($accion==='oferta_individual'){
      // Ventana individual: solo cambia el responsable de UNA asignatura del aula.
      // No interviene en las casillas del editor general por docente.
      $asig=(int)($_POST['asignatura_id']??0);
      $docenteRecibido=$_POST['docente_id']??null;
      if(!is_scalar($docenteRecibido)||!preg_match('/^(0|[1-9][0-9]*)$/D',(string)$docenteRecibido))
        throw new RuntimeException('Selecciona un docente o la opción Sin docente.');
      $doc=(int)$docenteRecibido;
      $versionEsperada=(string)($_POST['version_oferta']??'');
      if($asig<=0||!preg_match('/^(0|[1-9][0-9]*):[01]:(0|[1-9][0-9]*)$/D',$versionEsperada))
        throw new RuntimeException('Selecciona una asignatura válida.');
      // Cero es la acción explícita "Sin docente", no un ID de usuario.
      if($doc>0)sgaExigirDocenteDisponibleEnAula($doc,$pid,$jornadaAulaId);
      // Bloqueo de aula: previene escrituras simultáneas con la asignación múltiple.
      $bloqueo=$conexion->prepare('SELECT id FROM aulas_periodo WHERE id=? FOR UPDATE');
      if(!$bloqueo)throw new RuntimeException('No se pudo bloquear el aula.');
      $bloqueo->bind_param('i',$apId);
      sgaEjecutar($bloqueo,'bloquear aula para la asignación individual');
      $bloqueo->close();
      // Sin modificar historial: los cambios nuevos solo usan materias habilitadas para esta jornada.
      if($doc>0 && !sgaAsignaturasHabilitadaEnJornada($conexion,$asig,$jornadaAulaId))
        throw new RuntimeException('La asignatura no esta habilitada para la jornada de esta aula.');
      // No aceptar materias de otra aula aunque alguien altere el formulario.
      $verificar=$conexion->prepare('SELECT s.id FROM asignaturas s JOIN areas ar ON ar.id=s.area_id LEFT JOIN aula_asignaturas_seleccionadas sel ON sel.aula_periodo_id=? AND sel.asignatura_id=s.id LEFT JOIN ofertas_academicas ofa ON ofa.aula_periodo_id=? AND ofa.asignatura_id=s.id WHERE s.id=? AND s.activo=1 AND ar.activo=1 AND (sel.seleccionada=1 OR ofa.activo=1) LIMIT 1');
      if(!$verificar)throw new RuntimeException('No fue posible validar las asignaturas seleccionadas del aula.');
      $verificar->bind_param('iii',$apId,$apId,$asig);
      sgaEjecutar($verificar,'validar que la asignatura pertenece al aula');
      $permitida=(bool)$verificar->get_result()->fetch_row();
      $verificar->close();
      if(!$permitida)throw new RuntimeException('Esta asignatura ya no está seleccionada en el aula. Actualiza la página.');
      $actual=$conexion->prepare('SELECT id,asignatura_id,docente_id,activo FROM ofertas_academicas WHERE aula_periodo_id=? AND asignatura_id=? FOR UPDATE');
      if(!$actual)throw new RuntimeException('No se pudo consultar la asignación actual.');
      $actual->bind_param('ii',$apId,$asig);
      sgaEjecutar($actual,'consultar responsable actual de la materia');
      $antes=$actual->get_result()->fetch_assoc()?:null;
      $actual->close();
      $versionReal=$antes?((int)$antes['id'].':'.(int)$antes['activo'].':'.(int)$antes['docente_id']):'0:0:0';
      if(!hash_equals($versionReal,$versionEsperada))
        throw new RuntimeException('La asignación cambió mientras tenías abierto el formulario. Actualiza el aula e inténtalo nuevamente.');
      if($doc===0){
        // La columna docente_id es NOT NULL: conservar el antiguo ID para
        // trazabilidad y marcar la oferta inactiva, como en el editor múltiple.
        if(!$antes || (int)$antes['activo']!==1){
          flash('info','Esta asignatura ya se encuentra sin docente.');
        }else{
          $quitar=$conexion->prepare('UPDATE ofertas_academicas SET activo=0 WHERE id=? AND aula_periodo_id=? AND asignatura_id=? AND activo=1');
          if(!$quitar)throw new RuntimeException('No se pudo preparar la desvinculación del docente.');
          $idOferta=(int)$antes['id'];
          $quitar->bind_param('iii',$idOferta,$apId,$asig);
          sgaEjecutar($quitar,'retirar responsable desde la ventana individual');
          $filasActualizadas=$quitar->affected_rows;
          $quitar->close();
          if($filasActualizadas!==1)throw new RuntimeException('No fue posible dejar la asignatura sin docente. Recarga la página.');
          $despues=$antes;
          $despues['activo']=0;
          sgaAuditoriaObligatoria('UPDATE','Gestión académica','oferta_academica',$idOferta,
            'Docente retirado desde el diálogo individual; notas y asistencias históricas conservadas.',
            (int)$antes['docente_id'],$antes,$despues,'exito',null,null,'advertencia');
          flash('success','La asignatura quedó sin docente. Se conservó su historial académico.');
        }
      }elseif($antes && (int)$antes['activo']===1 && (int)$antes['docente_id']===$doc){
        flash('info','Este docente ya tiene asignada esa materia. No se modificó nada.');
      }else{
        $guardar=$conexion->prepare('INSERT INTO ofertas_academicas(aula_periodo_id,asignatura_id,docente_id,activo) VALUES(?,?,?,1) ON DUPLICATE KEY UPDATE docente_id=VALUES(docente_id),activo=1');
        if(!$guardar)throw new RuntimeException('No se pudo preparar la asignación del docente.');
        $guardar->bind_param('iii',$apId,$asig,$doc);
        sgaEjecutar($guardar,'asignar un docente a la materia');
        $guardar->close();
        $ver=$conexion->prepare('SELECT id,asignatura_id,docente_id,activo FROM ofertas_academicas WHERE aula_periodo_id=? AND asignatura_id=? LIMIT 1');
        $ver->bind_param('ii',$apId,$asig);
        sgaEjecutar($ver,'comprobar asignación individual guardada');
        $despues=$ver->get_result()->fetch_assoc();
        $ver->close();
        asignarRolPeriodo($doc,'docente',$pid);
        sgaAuditoriaObligatoria($antes?'UPDATE':'CREATE','Gestión académica','oferta_academica',$despues['id']??null,'Docente responsable asignado desde el diálogo individual.', $doc,$antes,$despues,'exito',null,null,'advertencia');
        flash('success',$antes?'Docente actualizado correctamente para esta asignatura.':'Docente asignado correctamente a la asignatura.');
      }
    }elseif($accion==='oferta'){
      $asig=(int)($_POST['asignatura_id']??0);$doc=(int)($_POST['docente_id']??0);if(!$asig||!$doc)throw new Exception('Selecciona asignatura y docente.');sgaExigirDocenteDisponibleEnAula($doc,$pid,$jornadaAulaId);if(!sgaAsignaturasHabilitadaEnJornada($conexion,$asig,$jornadaAulaId))throw new RuntimeException('La asignatura no esta habilitada en esta jornada.');$stmt=$conexion->prepare('SELECT s.id FROM asignaturas s JOIN areas ar ON ar.id=s.area_id WHERE s.id=? AND s.activo=1 AND ar.activo=1 LIMIT 1');$stmt->bind_param('i',$asig);$stmt->execute();$valida=$stmt->get_result()->fetch_assoc();$stmt->close();if(!$valida)throw new Exception('La asignatura o su área están desactivadas.');$stmt=$conexion->prepare('SELECT id,docente_id,activo FROM ofertas_academicas WHERE aula_periodo_id=? AND asignatura_id=? LIMIT 1');$stmt->bind_param('ii',$apId,$asig);$stmt->execute();$antes=$stmt->get_result()->fetch_assoc();$stmt->close();$stmt=$conexion->prepare('INSERT INTO ofertas_academicas(aula_periodo_id,asignatura_id,docente_id,activo) VALUES(?,?,?,1) ON DUPLICATE KEY UPDATE docente_id=VALUES(docente_id),activo=1');$stmt->bind_param('iii',$apId,$asig,$doc);$stmt->execute();$stmt->close();$stmt=$conexion->prepare('SELECT id,docente_id,activo FROM ofertas_academicas WHERE aula_periodo_id=? AND asignatura_id=? LIMIT 1');$stmt->bind_param('ii',$apId,$asig);$stmt->execute();$despues=$stmt->get_result()->fetch_assoc();$stmt->close();asignarRolPeriodo($doc,'docente',$pid);sgaAuditoriaObligatoria($antes?'UPDATE':'CREATE','Gestión académica','oferta_academica',$despues['id']??null,'Asignatura y docente guardados para el paralelo.',$doc,$antes,$despues,'exito',null,null,'advertencia');flash('success','Asignatura y docente guardados para el periodo.');
    }elseif($accion==='editar_oferta'){
      $oid=(int)($_POST['oferta_id']??0);$doc=(int)($_POST['docente_id']??0);if(!$oid||!$doc)throw new Exception('Asignación o docente inválido.');sgaExigirDocenteDisponibleEnAula($doc,$pid,$jornadaAulaId);$stmt=$conexion->prepare('SELECT id,asignatura_id,docente_id,activo FROM ofertas_academicas WHERE id=? AND aula_periodo_id=? LIMIT 1');$stmt->bind_param('ii',$oid,$apId);$stmt->execute();$antes=$stmt->get_result()->fetch_assoc();$stmt->close();if(!$antes)throw new Exception('Asignación no encontrada.');if(!sgaAsignaturasHabilitadaEnJornada($conexion,(int)$antes['asignatura_id'],$jornadaAulaId))throw new RuntimeException('Asignatura no habilitada para la jornada del aula.');$stmt=$conexion->prepare('UPDATE ofertas_academicas SET docente_id=? WHERE id=?');$stmt->bind_param('ii',$doc,$oid);$stmt->execute();$stmt->close();$despues=$antes;$despues['docente_id']=$doc;asignarRolPeriodo($doc,'docente',$pid);sgaAuditoriaObligatoria('UPDATE','Gestión académica','oferta_academica',$oid,'Docente responsable de la asignatura actualizado.',$doc,$antes,$despues,'exito',null,null,'advertencia');flash('success','Docente de la asignatura actualizado.');
    }elseif($accion==='toggle_oferta'){
      $oid=(int)$_POST['oferta_id'];$stmt=$conexion->prepare('SELECT id,asignatura_id,docente_id,activo FROM ofertas_academicas WHERE id=? AND aula_periodo_id=? LIMIT 1');$stmt->bind_param('ii',$oid,$apId);$stmt->execute();$antes=$stmt->get_result()->fetch_assoc();$stmt->close();if(!$antes)throw new Exception('Asignación no encontrada.');$nuevo=(int)$antes['activo']?0:1;if($nuevo){if(!sgaAsignaturasHabilitadaEnJornada($conexion,(int)$antes['asignatura_id'],$jornadaAulaId))throw new RuntimeException('Asignatura no habilitada para la jornada del aula.');$stmt=$conexion->prepare('SELECT s.id FROM asignaturas s JOIN areas ar ON ar.id=s.area_id WHERE s.id=? AND s.activo=1 AND ar.activo=1 LIMIT 1');$stmt->bind_param('i',$antes['asignatura_id']);$stmt->execute();$permitida=$stmt->get_result()->fetch_assoc();$stmt->close();if(!$permitida)throw new Exception('Activa primero la asignatura y su área.');}$stmt=$conexion->prepare('UPDATE ofertas_academicas SET activo=? WHERE id=?');$stmt->bind_param('ii',$nuevo,$oid);$stmt->execute();$stmt->close();$despues=$antes;$despues['activo']=$nuevo;sgaAuditoriaObligatoria('UPDATE','Gestión académica','oferta_academica',$oid,$nuevo?'Asignación académica activada.':'Asignación académica desactivada.',$antes['docente_id'],$antes,$despues,'exito',null,null,'advertencia');flash('success',$nuevo?'Asignación activada.':'Asignación desactivada.');
    }elseif($accion==='eliminar_oferta'){
      $oid=(int)$_POST['oferta_id'];$stmt=$conexion->prepare('SELECT id,asignatura_id,docente_id,activo FROM ofertas_academicas WHERE id=? AND aula_periodo_id=? LIMIT 1');$stmt->bind_param('ii',$oid,$apId);$stmt->execute();$antes=$stmt->get_result()->fetch_assoc();$stmt->close();if(!$antes)throw new Exception('Asignación no encontrada.');$stmt=$conexion->prepare("SELECT (SELECT COUNT(*) FROM calificaciones_trimestre WHERE oferta_id=?)+(SELECT COUNT(*) FROM notas_finales WHERE oferta_id=?)+(SELECT COUNT(*) FROM asistencia_sesiones WHERE oferta_id=?)+(SELECT COUNT(*) FROM configuracion_aportes WHERE oferta_id=?) c");$stmt->bind_param('iiii',$oid,$oid,$oid,$oid);$stmt->execute();$dep=(int)$stmt->get_result()->fetch_assoc()['c'];$stmt->close();if($dep>0)throw new Exception('La asignación ya tiene notas, asistencia o configuración. Desactívala en lugar de eliminarla.');$stmt=$conexion->prepare('DELETE FROM ofertas_academicas WHERE id=?');$stmt->bind_param('i',$oid);$stmt->execute();$stmt->close();sgaAuditoriaObligatoria('DELETE','Gestión académica','oferta_academica',$oid,'Asignación académica sin historial eliminada.',$antes['docente_id'],$antes,null,'exito',null,null,'critica');flash('success','Asignación eliminada.');
    }elseif($accion==='guardar_asignaturas'){
      // Aun sin docente, la materia puede formar parte del aula.
      $recibidas=$_POST['asignaturas']??[];
      if(!is_array($recibidas))throw new RuntimeException('Seleccion de asignaturas no valida.');
      foreach($recibidas as $valor){if(!is_scalar($valor)||!preg_match('/^[0-9]+$/',(string)$valor))throw new RuntimeException('Identificador de asignatura no valido.');}
      $ids=array_values(array_unique(array_filter(array_map('intval',$recibidas),static function($v){return $v>0;})));
      if(count($ids)>500)throw new RuntimeException('La seleccion supera el maximo permitido.');
      if($ids){
        $idSql=implode(',',$ids); // IDs enteros validados, nunca texto del usuario.
        $jid=(int)$jornadaAulaId;
        $conteo=$conexion->query("SELECT COUNT(*) c FROM asignaturas s JOIN areas ar ON ar.id=s.area_id WHERE s.id IN ($idSql) AND s.activo=1 AND ar.activo=1 AND FIND_IN_SET($jid,s.jornadas_ids)>0 AND FIND_IN_SET($jid,ar.jornadas_ids)>0")->fetch_assoc();
        if((int)($conteo['c']??0)!==count($ids))throw new RuntimeException('Hay asignaturas no vigentes o no autorizadas en la seleccion.');
      }
      $anteriores=[];
      $stmt=$conexion->prepare('SELECT asignatura_id FROM aula_asignaturas_seleccionadas WHERE aula_periodo_id=? AND seleccionada=1');
      $stmt->bind_param('i',$apId);sgaEjecutar($stmt,'consultar asignaturas seleccionadas');
      foreach($stmt->get_result()->fetch_all(MYSQLI_ASSOC) as $fila)$anteriores[]=(int)$fila['asignatura_id'];
      $stmt->close();
      $jid=(int)$jornadaAulaId;
      $stmt=$conexion->prepare("UPDATE aula_asignaturas_seleccionadas t
        JOIN asignaturas s ON s.id=t.asignatura_id
        JOIN areas ar ON ar.id=s.area_id
        SET t.seleccionada=0 WHERE t.aula_periodo_id=?
        AND FIND_IN_SET($jid,s.jornadas_ids)>0 AND FIND_IN_SET($jid,ar.jornadas_ids)>0");
      $stmt->bind_param('i',$apId);sgaEjecutar($stmt,'preparar la seleccion de asignaturas');$stmt->close();
      $insert=$conexion->prepare('INSERT INTO aula_asignaturas_seleccionadas(aula_periodo_id,asignatura_id,seleccionada) VALUES(?,?,1) ON DUPLICATE KEY UPDATE seleccionada=1');
      if(!$insert)throw new RuntimeException('No se pudo preparar la seleccion de asignaturas.');
      foreach($ids as $id){$insert->bind_param('ii',$apId,$id);sgaEjecutar($insert,'guardar asignatura seleccionada');}
      $insert->close();
      // Si se desmarca una materia que tenia docente, se DESACTIVA su oferta:
      // las calificaciones y asistencias no se eliminan ni cambian de ID.
      $jid=(int)$jornadaAulaId;
      $q=$conexion->prepare("SELECT o.id,o.asignatura_id,o.docente_id FROM ofertas_academicas o
        JOIN asignaturas s ON s.id=o.asignatura_id JOIN areas ar ON ar.id=s.area_id
        WHERE o.aula_periodo_id=? AND o.activo=1
        AND FIND_IN_SET($jid,s.jornadas_ids)>0 AND FIND_IN_SET($jid,ar.jornadas_ids)>0");
      $q->bind_param('i',$apId);sgaEjecutar($q,'consultar asignaciones existentes');
      $ofertasActivas=$q->get_result()->fetch_all(MYSQLI_ASSOC);$q->close();
      $desactivadas=0;
      $cerrar=$conexion->prepare('UPDATE ofertas_academicas SET activo=0 WHERE id=? AND aula_periodo_id=?');
      foreach($ofertasActivas as $of){
        if(in_array((int)$of['asignatura_id'],$ids,true))continue;
        $oid=(int)$of['id'];$cerrar->bind_param('ii',$oid,$apId);sgaEjecutar($cerrar,'desactivar oferta no seleccionada');
        $desactivadas++;
        sgaAuditoriaObligatoria('UPDATE','Gestion academica','oferta_academica',$oid,'Oferta desactivada al retirar la asignatura del aula.',(int)$of['docente_id'],['activo'=>1],['activo'=>0],'exito',null,null,'advertencia');
      }
      $cerrar->close();
      sgaAuditoriaObligatoria('UPDATE','Gestion academica','aula_asignaturas',$apId,'Seleccion de asignaturas del aula actualizada.',null,['asignaturas'=>$anteriores],['asignaturas'=>$ids],'exito',null,null,'advertencia');
      flash('success','Asignaturas guardadas: '.count($ids).'.'.($desactivadas?' Asignaciones desactivadas: '.$desactivadas.' (historial conservado).':''));
    }elseif($accion==='guardar_docentes'){
      // Editor por DOCENTE: las casillas muestran las asignaturas de este aula.
      // Las marcadas ya pertenecen al docente elegido. Las desmarcadas no.
      $docenteElegido=(int)($_POST['docente_id']??0);
      sgaExigirDocenteDisponibleEnAula($docenteElegido,$pid,$jornadaAulaId);
      $seleccionPost=$_POST['asignaturas_docente']??[];
      $originales=$_POST['docentes_originales']??[];
      if(!is_array($seleccionPost)||!is_array($originales)||count($seleccionPost)>1000||count($originales)>1000)
        throw new RuntimeException('La selección de asignaturas no tiene un formato válido.');
      $seleccionadasDocente=[];
      foreach($seleccionPost as $valor){
        if(!is_scalar($valor)||!preg_match('/^[1-9][0-9]*$/',(string)$valor))
          throw new RuntimeException('Se recibió una asignatura inválida.');
        $seleccionadasDocente[(int)$valor]=true;
      }
      // Serializar el guardado dentro del aula y leer los responsables actuales.
      $bloqueo=$conexion->prepare('SELECT id FROM aulas_periodo WHERE id=? FOR UPDATE');
      if(!$bloqueo)throw new RuntimeException('No se pudo bloquear el aula.');
      $bloqueo->bind_param('i',$apId);sgaEjecutar($bloqueo,'bloquear el aula');$bloqueo->close();
      $jid=(int)$jornadaAulaId;
      $consulta=$conexion->prepare("SELECT s.id FROM asignaturas s JOIN areas ar ON ar.id=s.area_id LEFT JOIN aula_asignaturas_seleccionadas t ON t.aula_periodo_id=? AND t.asignatura_id=s.id LEFT JOIN ofertas_academicas o ON o.aula_periodo_id=? AND o.asignatura_id=s.id WHERE s.activo=1 AND ar.activo=1 AND FIND_IN_SET($jid,s.jornadas_ids)>0 AND FIND_IN_SET($jid,ar.jornadas_ids)>0 AND COALESCE(o.evaluacion_aula,0)=0 AND COALESCE(o.evaluacion_parametros_historica,0)=0 AND (t.seleccionada=1 OR o.activo=1)");
      if(!$consulta)throw new RuntimeException('Falta instalar el SQL de asignaturas del aula.');
      $consulta->bind_param('ii',$apId,$apId);sgaEjecutar($consulta,'validar asignaturas del aula');
      $permitidas=[];
      foreach($consulta->get_result()->fetch_all(MYSQLI_ASSOC) as $fila)$permitidas[(int)$fila['id']]=true;
      $consulta->close();
      foreach($seleccionadasDocente as $materiaId=>$_){
        if(!isset($permitidas[$materiaId]))throw new RuntimeException('Una asignatura marcada ya no pertenece a esta aula.');
      }
      $buscar=$conexion->prepare('SELECT id,asignatura_id,docente_id,activo FROM ofertas_academicas WHERE aula_periodo_id=? FOR UPDATE');
      if(!$buscar)throw new RuntimeException('No se pudieron consultar las asignaciones.');
      $buscar->bind_param('i',$apId);sgaEjecutar($buscar,'consultar asignaciones');
      $anteriores=[];
      foreach($buscar->get_result()->fetch_all(MYSQLI_ASSOC) as $fila)$anteriores[(int)$fila['asignatura_id']]=$fila;
      $buscar->close();
      // Comparar con la pantalla original para no sobrescribir cambios
      // efectuados por otro administrador mientras se usaba el diálogo.
      foreach($permitidas as $materiaId=>$_){
        $valor=$originales[$materiaId]??null;
        if(!is_scalar($valor)||!preg_match('/^(0|[1-9][0-9]*)$/',(string)$valor))
          throw new RuntimeException('La lista de asignaturas ha cambiado. Recarga el aula antes de guardar.');
        $anterior=$anteriores[$materiaId]??null;
        $dueñoActual=$anterior && (int)$anterior['activo']===1?(int)$anterior['docente_id']:0;
        if((int)$valor!==$dueñoActual)
          throw new RuntimeException('Otro usuario modificó las asignaciones de esta aula. Recarga antes de guardar.');
      }
      $guardar=$conexion->prepare('INSERT INTO ofertas_academicas(aula_periodo_id,asignatura_id,docente_id,activo) VALUES(?,?,?,1) ON DUPLICATE KEY UPDATE docente_id=VALUES(docente_id),activo=1');
      $desactivar=$conexion->prepare('UPDATE ofertas_academicas SET activo=0 WHERE id=? AND aula_periodo_id=? AND docente_id=? AND activo=1');
      if(!$guardar||!$desactivar)throw new RuntimeException('No fue posible preparar la actualización.');
      $nuevas=0;$reactivadas=0;$transferidas=0;$retiradas=0;
      foreach($permitidas as $materiaId=>$_){
        $anterior=$anteriores[$materiaId]??null;
        $dueñoActual=$anterior && (int)$anterior['activo']===1?(int)$anterior['docente_id']:0;
        $marcada=isset($seleccionadasDocente[$materiaId]);
        if($marcada){
          if($dueñoActual===$docenteElegido)continue; // Ya es de este docente.
          $guardar->bind_param('iii',$apId,$materiaId,$docenteElegido);
          sgaEjecutar($guardar,'asignar la materia al docente elegido');
          $posterior=$anterior?:['id'=>(int)$conexion->insert_id,'asignatura_id'=>$materiaId];
          $posterior['docente_id']=$docenteElegido;$posterior['activo']=1;
          if(!$anterior)$nuevas++;
          elseif($dueñoActual>0)$transferidas++;
          else $reactivadas++;
          sgaAuditoriaObligatoria($anterior?'UPDATE':'CREATE','Gestión académica','oferta_academica',$posterior['id']??null,
            $dueñoActual>0?'Asignatura transferida expresamente desde el editor por docente.':'Asignatura asignada desde el editor por docente.',
            $docenteElegido,$anterior,$posterior,'exito',null,null,'advertencia');
        }elseif($dueñoActual===$docenteElegido){
          // Desmarcar solo retira las materias DEL docente seleccionado.
          // No altera asignaciones de otros docentes.
          $idOferta=(int)$anterior['id'];
          $desactivar->bind_param('iii',$idOferta,$apId,$docenteElegido);
          sgaEjecutar($desactivar,'retirar asignación del docente');
          $posterior=$anterior;$posterior['activo']=0;$retiradas++;
          sgaAuditoriaObligatoria('UPDATE','Gestión académica','oferta_academica',$idOferta,
            'Asignatura desmarcada para este docente; historial conservado.',
            $docenteElegido,$anterior,$posterior,'exito',null,null,'advertencia');
        }
      }
      $guardar->close();$desactivar->close();
      if($nuevas+$reactivadas+$transferidas>0)asignarRolPeriodo($docenteElegido,'docente',$pid);
      if($nuevas+$reactivadas+$transferidas+$retiradas===0){
        flash('info','No se realizaron cambios en las asignaturas de este docente.');
      }else{
        flash('success',"Asignaciones guardadas: $nuevas nuevas, $reactivadas reactivadas, $transferidas transferidas y $retiradas retiradas. Las demás no se modificaron.");
      }
    }elseif($accion==='retirar'){
      $mid=(int)($_POST['matricula_id']??0);$stmt=$conexion->prepare('SELECT id,estudiante_id,estado,numero_lista FROM matriculas WHERE id=? AND aula_periodo_id=? LIMIT 1');$stmt->bind_param('ii',$mid,$apId);$stmt->execute();$antes=$stmt->get_result()->fetch_assoc();$stmt->close();if(!$antes)throw new Exception('Matrícula no encontrada.');$stmt=$conexion->prepare("UPDATE matriculas SET estado='retirado' WHERE id=?");$stmt->bind_param('i',$mid);$stmt->execute();$stmt->close();$despues=$antes;$despues['estado']='retirado';sgaAuditoriaObligatoria('UPDATE','Matrículas','matricula',$mid,'Estudiante retirado del paralelo.',(int)$antes['estudiante_id'],$antes,$despues,'exito',null,null,'advertencia');flash('success','Estudiante retirado.');
    }elseif($accion==='reactivar'){
      $mid=(int)($_POST['matricula_id']??0);$stmt=$conexion->prepare('SELECT estudiante_id FROM matriculas WHERE id=? AND aula_periodo_id=? LIMIT 1');$stmt->bind_param('ii',$mid,$apId);$stmt->execute();$m=$stmt->get_result()->fetch_assoc();$stmt->close();if(!$m)throw new Exception('Matrícula no encontrada.');$conexion->begin_transaction();$r=matricularUsuarioEnAula((int)$m['estudiante_id'],$apId,$pid);if(!in_array($r['estado'],['reactivado','existente'],true))throw new Exception($r['mensaje']??'No se pudo reactivar.');if($r['estado']==='reactivado')sgaAuditoriaObligatoria('UPDATE','Matrículas','matricula',$mid,'Matrícula reactivada desde administración.',(int)$m['estudiante_id'],['estado'=>'retirado'],['estado'=>'activo'],'exito',null,null,'advertencia');if(!$conexion->commit())throw new RuntimeException('No se pudo confirmar la reactivacion.');flash('success','Matrícula reactivada.');
    }elseif($accion==='reordenar_alfabeticamente'){
      // Control adicional frente a solicitudes externas: la autorizacion del aula
      // y el estado del periodo ya se validaron al entrar a este controlador.
      $csrfEnviado=(string)($_POST['csrf_reordenar_aula']??'');
      if(!hash_equals((string)$_SESSION['csrf_reordenar_aula'],$csrfEnviado)){
        throw new RuntimeException('La solicitud de ordenamiento ha caducado. Actualiza la página y vuelve a intentarlo.');
      }

      // El bloqueo del aula serializa este proceso con las matriculas nuevas y
      // con las modificaciones manuales del numero de lista.
      $bloqueo=$conexion->prepare('SELECT id FROM aulas_periodo WHERE id=? FOR UPDATE');
      if(!$bloqueo)throw new RuntimeException('No se pudo bloquear el aula para ordenar.');
      $bloqueo->bind_param('i',$apId);
      sgaEjecutar($bloqueo,'bloquear la numeracion del aula');
      $bloqueo->close();

      // Solo estudiantes activos: las matriculas retiradas/finalizadas conservan
      // su historial y numero anterior. Orden por APELLIDOS y luego NOMBRES.
      $consulta=$conexion->prepare("SELECT m.id,m.numero_lista
          FROM matriculas m
          INNER JOIN usuarios u ON u.id=m.estudiante_id
          WHERE m.aula_periodo_id=? AND m.estado='activo'
          ORDER BY TRIM(u.apellidos) COLLATE utf8mb4_unicode_ci,
                   TRIM(u.nombres) COLLATE utf8mb4_unicode_ci,
                   u.cedula,m.id
          FOR UPDATE");
      if(!$consulta)throw new RuntimeException('No se pudo obtener la lista de estudiantes.');
      $consulta->bind_param('i',$apId);
      sgaEjecutar($consulta,'consultar los estudiantes en orden alfabetico');
      $filasOrdenadas=$consulta->get_result()->fetch_all(MYSQLI_ASSOC);
      $consulta->close();
      if(!$filasOrdenadas)throw new RuntimeException('No hay estudiantes activos para ordenar en este aula.');

      $actualiza=$conexion->prepare("UPDATE matriculas
          SET numero_lista=? WHERE id=? AND aula_periodo_id=? AND estado='activo'");
      if(!$actualiza)throw new RuntimeException('No se pudo preparar el nuevo orden de lista.');
      $total=0;$cambios=0;$ordenAnterior=[];$ordenNuevo=[];
      foreach($filasOrdenadas as $fila){
        $total++;
        $mid=(int)$fila['id'];
        $anterior=$fila['numero_lista']===null?null:(int)$fila['numero_lista'];
        $ordenAnterior[]=['matricula_id'=>$mid,'numero_lista'=>$anterior];
        $ordenNuevo[]=['matricula_id'=>$mid,'numero_lista'=>$total];
        if($anterior===$total)continue;
        $actualiza->bind_param('iii',$total,$mid,$apId);
        sgaEjecutar($actualiza,'guardar el nuevo numero de lista');
        $cambios++;
      }
      $actualiza->close();
      sgaAuditoriaObligatoria('REORDER','Matrículas','aula_periodo',$apId,
          'Estudiantes activos ordenados alfabéticamente por apellidos y nombres.',
          null,
          ['aula_periodo_id'=>$apId,'lista'=>$ordenAnterior],
          ['aula_periodo_id'=>$apId,'lista'=>$ordenNuevo],
          'exito',null,null,'advertencia');
      flash('success',"Orden alfabético guardado en la base de datos: $total estudiantes activos, $cambios números actualizados.");
    }elseif($accion==='editar_matricula'){
      $mid=(int)($_POST['matricula_id']??0);$numero=trim((string)($_POST['numero_lista']??''));$numero=$numero===''?null:(int)$numero;if($numero!==null&&$numero<1)throw new Exception('El número de lista debe ser mayor que cero.');$stmt=$conexion->prepare('SELECT id,estudiante_id,numero_lista,estado FROM matriculas WHERE id=? AND aula_periodo_id=? LIMIT 1');$stmt->bind_param('ii',$mid,$apId);$stmt->execute();$antes=$stmt->get_result()->fetch_assoc();$stmt->close();if(!$antes)throw new Exception('Matrícula no encontrada.');if($numero!==null){
        // Serializar los cambios manuales con la asignacion automatica de lista.
        $bloqueo=$conexion->prepare('SELECT id FROM aulas_periodo WHERE id=? FOR UPDATE');
        $bloqueo->bind_param('i',$apId);sgaEjecutar($bloqueo,'bloquear la numeracion del paralelo');$bloqueo->close();
        $dup=$conexion->prepare("SELECT id FROM matriculas WHERE aula_periodo_id=? AND numero_lista=? AND estado='activo' AND id<>? LIMIT 1");$dup->bind_param('iii',$apId,$numero,$mid);sgaEjecutar($dup,'validar numero de lista');$existeNumero=$dup->get_result()->fetch_assoc();$dup->close();if($existeNumero)throw new Exception('Ese número de lista ya está asignado a otro estudiante activo.');}if($numero===null){$stmt=$conexion->prepare('UPDATE matriculas SET numero_lista=NULL WHERE id=?');$stmt->bind_param('i',$mid);}else{$stmt=$conexion->prepare('UPDATE matriculas SET numero_lista=? WHERE id=?');$stmt->bind_param('ii',$numero,$mid);}$stmt->execute();$stmt->close();$despues=$antes;$despues['numero_lista']=$numero;sgaAuditoriaObligatoria('UPDATE','Matrículas','matricula',$mid,'Número de lista de la matrícula actualizado.',(int)$antes['estudiante_id'],$antes,$despues,'exito',null,null,'info');flash('success','Matrícula actualizada.');
    }elseif($accion==='eliminar_matricula'){
      $mid=(int)($_POST['matricula_id']??0);$stmt=$conexion->prepare('SELECT id,estudiante_id,numero_lista,estado FROM matriculas WHERE id=? AND aula_periodo_id=? LIMIT 1');$stmt->bind_param('ii',$mid,$apId);$stmt->execute();$antes=$stmt->get_result()->fetch_assoc();$stmt->close();if(!$antes)throw new Exception('Matrícula no encontrada.');$uid=(int)$antes['estudiante_id'];$stmt=$conexion->prepare("SELECT (SELECT COUNT(*) FROM calificaciones_trimestre WHERE matricula_id=?)+(SELECT COUNT(*) FROM notas_finales WHERE matricula_id=?)+(SELECT COUNT(*) FROM asistencia_detalle WHERE matricula_id=?)+(SELECT COUNT(*) FROM eleccion_votos WHERE estudiante_id=? AND aula_periodo_id=?)+(SELECT COUNT(*) FROM sga_calificaciones_parametros WHERE matricula_id=?) c");$stmt->bind_param('iiiiii',$mid,$mid,$mid,$uid,$apId,$mid);$stmt->execute();$dep=(int)$stmt->get_result()->fetch_assoc()['c'];$stmt->close();if($dep>0)throw new Exception('La matrícula ya tiene calificaciones, asistencia o voto electoral. Retira al estudiante en lugar de eliminarla.');$stmt=$conexion->prepare('DELETE FROM matriculas WHERE id=?');$stmt->bind_param('i',$mid);$stmt->execute();$stmt->close();sgaAuditoriaObligatoria('DELETE','Matrículas','matricula',$mid,'Matrícula sin historial eliminada.',$uid,$antes,null,'exito',null,null,'critica');flash('success','Matrícula eliminada.');
    }
    if($sgaTransaccionSimple && !$conexion->commit())throw new RuntimeException('No se pudieron confirmar los cambios academicos.');
  }catch(Throwable $e){try{$conexion->rollback();}catch(Throwable $x){}flash('error',$e->getMessage());}
  redir('modulos/academico/aula.php?id='.$apId);
}

$soloLectura=false;
$stmtEstado=$conexion->prepare('SELECT estado FROM periodos_academicos WHERE id=? LIMIT 1');
$stmtEstado->bind_param('i',$pid);sgaEjecutar($stmtEstado,'consultar el estado del periodo');
$soloLectura=($stmtEstado->get_result()->fetch_assoc()['estado']??'')==='cerrado';$stmtEstado->close();
$editarOfertaId=(int)($_GET['editar_oferta']??0);$editarOferta=null;if($editarOfertaId){$stmt=$conexion->prepare('SELECT o.*,s.nombre asignatura,ar.nombre area FROM ofertas_academicas o JOIN asignaturas s ON s.id=o.asignatura_id JOIN areas ar ON ar.id=s.area_id WHERE o.id=? AND o.aula_periodo_id=? LIMIT 1');$stmt->bind_param('ii',$editarOfertaId,$apId);$stmt->execute();$editarOferta=$stmt->get_result()->fetch_assoc()?:null;$stmt->close();}
$stmt=$conexion->prepare("SELECT m.id matricula_id,m.numero_lista,m.estado,u.id usuario_id,u.cedula,u.apellidos,u.nombres FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id WHERE m.aula_periodo_id=? ORDER BY FIELD(m.estado,'activo','retirado','finalizado'),COALESCE(m.numero_lista,9999),u.apellidos,u.nombres");$stmt->bind_param('i',$apId);$stmt->execute();$matriculas=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
$stmt=$conexion->prepare("SELECT o.id,o.asignatura_id,o.activo,s.nombre asignatura,s.codigo,ar.nombre area,ar.orden area_orden,u.id docente_id,u.cedula docente_cedula,CONCAT(u.apellidos,' ',u.nombres) docente FROM ofertas_academicas o JOIN asignaturas s ON s.id=o.asignatura_id JOIN areas ar ON ar.id=s.area_id JOIN usuarios u ON u.id=o.docente_id WHERE o.aula_periodo_id=? AND o.evaluacion_aula=0 AND o.evaluacion_parametros_historica=0 ORDER BY o.activo DESC,ar.orden,s.nombre");$stmt->bind_param('i',$apId);$stmt->execute();$ofertas=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
// Filtrado por jornada DEL AULA, tanto para el Administrador como el Subadministrador.
$jid=(int)$jornadaAulaId;
$asigs=$conexion->query("SELECT s.*,ar.nombre area,ar.id area_id FROM asignaturas s JOIN areas ar ON ar.id=s.area_id WHERE s.activo=1 AND ar.activo=1 AND s.archivado_en IS NULL AND ar.archivado_en IS NULL AND FIND_IN_SET($jid,s.jornadas_ids)>0 AND FIND_IN_SET($jid,ar.jornadas_ids)>0 ORDER BY ar.orden,s.nombre")->fetch_all(MYSQLI_ASSOC);
// El subadministrador ve docentes de la jornada del aula, segun el periodo;
// el administrador principal conserva acceso a todos los docentes activos.
$consultaDocentes = 'SELECT u.id,u.cedula,u.apellidos,u.nombres FROM usuarios u WHERE '
    .sgaFiltroDocentesDisponiblesEnAula($pid,$jornadaAulaId).' ORDER BY u.apellidos,u.nombres,u.cedula';
$personas = $conexion->query($consultaDocentes)->fetch_all(MYSQLI_ASSOC);
$ofertasParametros=sgaParametrosOfertasAula($conexion,$apId);$principalParametros=null;$historialParametros=[];
foreach($ofertasParametros as $op){if((int)$op['evaluacion_aula'])$principalParametros=$op;elseif((int)$op['ambitos'])$historialParametros[]=$op;}
if($modoParametros){$asigs=[];$ofertas=[];}
else{
  $reservadas=array_map('intval',array_column($ofertasParametros,'id'));
  // Las ofertas antiguas con parámetros no se editan como asignaturas normales.
  $s=$conexion->prepare('SELECT asignatura_id FROM ofertas_academicas WHERE aula_periodo_id=? AND (evaluacion_aula=1 OR evaluacion_parametros_historica=1)');
  $s->bind_param('i',$apId);sgaEjecutar($s,'separar registros históricos');$asigReservadas=array_map('intval',array_column($s->get_result()->fetch_all(MYSQLI_ASSOC),'asignatura_id'));$s->close();
  $asigs=array_values(array_filter($asigs,static fn($a)=>!in_array((int)$a['id'],$asigReservadas,true)));
}
// Las ofertas activas anteriores tambien cuentan como seleccionadas; el SQL
// de migracion no tiene que rehacer las relaciones historicas.
$stmt=$conexion->prepare('SELECT asignatura_id FROM aula_asignaturas_seleccionadas WHERE aula_periodo_id=? AND seleccionada=1');
if(!$stmt)throw new RuntimeException('Instala sql/SQL_SGA_SELECCION_ASIGNATURAS_AULA.sql antes de utilizar los nuevos flotantes.');
$stmt->bind_param('i',$apId);sgaEjecutar($stmt,'consultar asignaturas seleccionadas');
$seleccionadasIds=[];
foreach($stmt->get_result()->fetch_all(MYSQLI_ASSOC) as $sel)$seleccionadasIds[(int)$sel['asignatura_id']]=true;
$stmt->close();
$ofertasPorAsignatura=[];
foreach($ofertas as $oferta){
    $asigClave=(int)$oferta['asignatura_id'];
    $ofertasPorAsignatura[$asigClave]=$oferta;
    if((int)$oferta['activo']===1)$seleccionadasIds[$asigClave]=true;
}
$seleccionadasAula=[];$pendientesSinDocente=[];
foreach($asigs as $asigFila){
    $idAsig=(int)$asigFila['id'];
    if(!isset($seleccionadasIds[$idAsig]))continue;
    $seleccionadasAula[]=$asigFila;
    if(!isset($ofertasPorAsignatura[$idAsig]) || (int)$ofertasPorAsignatura[$idAsig]['activo']!==1)$pendientesSinDocente[]=$asigFila;
}

$stmt=$conexion->prepare("SELECT u.id,u.cedula,u.apellidos,u.nombres,(SELECT m.estado FROM matriculas m WHERE m.estudiante_id=u.id AND m.aula_periodo_id=? LIMIT 1) estado_previo FROM usuarios u WHERE u.activo=1 AND EXISTS(SELECT 1 FROM usuario_roles ur JOIN roles rr ON rr.id=ur.rol_id WHERE ur.usuario_id=u.id AND ur.periodo_id=? AND rr.codigo='estudiante') AND NOT EXISTS(SELECT 1 FROM matriculas m JOIN aulas_periodo x ON x.id=m.aula_periodo_id WHERE m.estudiante_id=u.id AND x.periodo_id=? AND m.estado='activo')".filtroUsuariosJornadasSQL($pid,'u')." ORDER BY u.apellidos,u.nombres LIMIT 1000");$stmt->bind_param('iii',$apId,$pid,$pid);$stmt->execute();$disponibles=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
$paralelosDestino=[];
$stmtDestino=$conexion->prepare("SELECT ap.id,a.nivel,a.nombre,a.paralelo FROM aulas_periodo ap JOIN aulas a ON a.id=ap.aula_id WHERE ap.periodo_id=? AND ap.id<>? AND ap.activo=1".filtroJornadasSQL($pid,'a')." ORDER BY a.nombre,a.paralelo");
$stmtDestino->bind_param('ii',$pid,$apId);sgaEjecutar($stmtDestino,'cargar las opciones de traslado');
$paralelosDestino=$stmtDestino->get_result()->fetch_all(MYSQLI_ASSOC);$stmtDestino->close();
$tituloPagina='Aula · '.$ap['aula'].' '.$ap['paralelo'];$subtituloPagina=$ap['nivel'].' · '.($ap['jornada']??'Sin jornada').' · Periodo '.$ap['periodo'];require __DIR__.'/../../partials/header.php';
?>
<?php if(!(int)$ap['activo']):?><div class="alert info">Esta aula está desactivada para el periodo. Puedes consultar y administrar su historial, pero conviene reactivarla desde Gestión académica antes de continuar la operación diaria.</div><?php endif;?>
<?php if($soloLectura):?><div class="notice" role="status"><strong>Período cerrado · solo consulta.</strong> No se pueden matricular estudiantes ni modificar asignaturas o docentes. Los reportes siguen disponibles.</div><?php endif;?>
<section class="card sga-aula-gestion-card">
  <div class="sga-aula-gestion-head">
    <div><h2>Gestión del aula</h2><p class="muted"><?= $modoParametros?'Administra las matrículas y el docente único responsable de todos los ámbitos.':'Administra las matrículas, las asignaturas del paralelo y sus docentes responsables.' ?></p></div>
    <span class="sga-aula-gestion-etiqueta"><?=e($ap['jornada']??'Sin jornada')?> · <?=e($ap['periodo'])?></span>
  </div>
  <div class="sga-aula-gestion-botones">
    <button type="button" class="btn btn-primary" data-sga-open="sga-modal-matricula" aria-haspopup="dialog" aria-controls="sga-modal-matricula">Matricular estudiantes</button>
    <?php if(!$modoParametros):?><button type="button" class="btn btn-secondary" data-sga-open="sga-modal-asignaturas" aria-haspopup="dialog" aria-controls="sga-modal-asignaturas">Seleccionar asignaturas</button>
    <button type="button" class="btn btn-secondary" data-sga-open="sga-modal-docentes" aria-haspopup="dialog" aria-controls="sga-modal-docentes">Asignar docentes</button><?php endif;?>
  </div>
</section>
<style>
.sga-aula-gestion-card{margin-bottom:18px}
.sga-aula-gestion-head{display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:10px}
.sga-aula-gestion-head h2{margin:0 0 4px}
.sga-aula-gestion-head p{margin:0}
.sga-aula-gestion-etiqueta{font-size:12px;white-space:nowrap;background:#edf4fe;border:1px solid #d9e5f5;border-radius:20px;color:#204e80;padding:7px 12px}
.sga-aula-gestion-botones{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}
.sga-aula-gestion-botones .btn{min-height:42px}
.sga-aula-modal{position:fixed;inset:0;margin:auto;padding:0;max-height:calc(100dvh - 32px);width:min(780px,calc(100vw - 28px));max-width:calc(100vw - 28px);overflow-y:auto;color:#142c48;background:#fff;border:1px solid #cfdff2;border-radius:15px;box-shadow:0 28px 80px rgba(4,20,41,.35)}
.sga-aula-modal:not([open]){display:none}
.sga-aula-modal::backdrop{background:rgba(3,20,43,.64)}
.sga-aula-modal-header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:20px 24px;border-bottom:1px solid #e2e9f3}
.sga-aula-modal-header h2{margin:0;color:#153c73;font-size:21px}
.sga-aula-modal-header p{font-size:13px;line-height:1.5;color:#586f88;margin:6px 0 0}
.sga-aula-modal-close{border:0;border-radius:9px;background:#eef3f9;color:#38536f;font-size:24px;line-height:1;width:36px;height:36px;flex:0 0 36px;cursor:pointer}
.sga-aula-modal-body{padding:20px 24px 24px}
.sga-aula-modal-footer{margin-top:18px;display:flex;justify-content:flex-end;gap:10px;flex-wrap:wrap}
.sga-aula-modal :is(button,a,input,select):focus-visible{outline:3px solid #4b90d2;outline-offset:2px}
.sga-aula-tabs{display:flex;gap:5px;border-bottom:1px solid #dce5f1;padding:0 24px}
.sga-aula-tab{border:0;background:transparent;color:#465e7b;padding:15px 20px 13px;border-bottom:3px solid transparent;font:inherit;font-weight:700;cursor:pointer}
.sga-aula-tab[aria-selected="true"]{color:#0059a8;border-bottom-color:#005ba7;background:#eff5ff}
.sga-aula-tab-panel[hidden]{display:none!important}
.sga-aula-lista [hidden]{display:none!important}
.sga-aula-lista{overflow-y:auto;max-height:min(40vh,370px);border:1px solid #dfe7f1;border-radius:11px;background:#fff;margin-top:10px}
.sga-aula-fila{display:flex!important;flex-direction:row!important;align-items:center;gap:11px;padding:11px 13px;border-bottom:1px solid #eef2f7;cursor:pointer;margin:0!important;font-size:13px}
.sga-aula-fila:last-child{border-bottom:0}
.sga-aula-fila:hover{background:#f5f9ff}
.sga-aula-fila input[type=checkbox]{width:17px;height:17px;flex:0 0 17px;margin:0}
.sga-aula-fila strong{display:block}
.sga-aula-fila small{display:block;margin-top:3px;color:#59708a;font-size:12px}
.sga-aula-estadisticas{font-size:12px;color:#54708b;font-weight:600}
.sga-aula-input-buscar{width:100%;margin-top:6px}
.sga-aula-select-todo{display:flex!important;flex-direction:row!important;align-items:center;gap:8px;font-weight:700;margin-top:14px}
.sga-aula-select-todo input{width:18px;height:18px;margin:0}
.sga-aula-ayuda{color:#63768a;font-size:12px;line-height:1.5;margin-top:8px}
.sga-aula-descarga{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;background:#f4f8fe;border:1px solid #dce8f6;border-radius:12px;padding:15px;margin-bottom:18px}
.sga-aula-descarga p{margin:0;flex:1 1 240px;line-height:1.55;font-size:13px;color:#455e78}
/* Asignación individual: una sola asignatura y un solo docente. */
#sga-modal-docente-individual{width:min(620px,calc(100vw - 24px));max-height:calc(100dvh - 24px)}
.sga-doc-ind-materia{padding:10px 13px;border:1px solid #dbe6f3;border-radius:10px;background:#f3f8fe;margin-bottom:11px}
.sga-doc-ind-materia .sga-doc-ind-etiqueta{font-weight:700;color:#50708e;font-size:11px;text-transform:uppercase;letter-spacing:.045em}
.sga-doc-ind-materia strong{display:block;margin:3px 0;font-size:14px;color:#163c6d;line-height:1.35}
.sga-doc-ind-materia small{display:block;color:#59718c;line-height:1.4}
.sga-doc-ind-materia .sga-doc-ind-actual{display:block;margin-top:4px;color:#274e76;font-size:12px;font-weight:650}
#sga-simple-buscar{width:100%;margin:5px 0 8px;min-height:40px}
.sga-doc-ind-opciones{max-height:min(39dvh,265px);overflow-y:auto;scrollbar-gutter:stable;border:1px solid #dce6f1;border-radius:10px;background:#fff}
.sga-doc-ind-opcion{display:flex!important;flex-direction:row!important;flex-wrap:nowrap;align-items:center!important;justify-content:flex-start;gap:11px;text-align:left!important;width:100%;min-height:54px;cursor:pointer;padding:9px 12px;margin:0!important;border-bottom:1px solid #edf1f7;font-weight:400!important}
.sga-doc-ind-opcion:last-child{border-bottom:0}
.sga-doc-ind-opcion:hover{background:#f2f7fe}
.sga-doc-ind-sin-docente{background:#f8fafc;border-bottom:2px solid #dce6f1}
.sga-doc-ind-sin-docente strong{color:#495f77}
.sga-doc-ind-opcion:has(input:checked){background:#eaf4ff;box-shadow:inset 3px 0 #1a67ac}
.sga-doc-ind-opcion[hidden]{display:none!important}
.sga-doc-ind-opcion input[type=radio]{display:block!important;width:18px!important;min-width:18px;max-width:18px;height:18px!important;flex:0 0 18px;align-self:center!important;padding:0!important;margin:0!important;border-radius:50%;accent-color:#175c9f}
.sga-doc-ind-opcion>span{display:block!important;flex:1 1 auto;min-width:0;text-align:left}.sga-doc-ind-opcion strong{display:block;color:#173959;line-height:1.3;font-size:12px;overflow-wrap:break-word}
.sga-doc-ind-opcion small{display:block;color:#677f95;font-size:11px;margin-top:2px}
.sga-doc-ind-resultado{margin:8px 0 0;font-size:12px;color:#4f6c86;min-height:16px;line-height:1.3}
.sga-doc-ind-vacio{padding:16px;text-align:center;color:#63788e;font-size:13px}
/* Editor por docente: buscar, escoger una persona y marcar sus asignaturas. */
#sga-modal-docentes{width:min(970px,calc(100vw - 24px));max-height:calc(100dvh - 24px)}
.sga-doc-columnas{display:grid;grid-template-columns:minmax(235px,300px) minmax(0,1fr);gap:12px;align-items:start}
.sga-doc-panel{border:1px solid #d8e3f1;border-radius:11px;overflow:hidden;background:#fff;min-width:0}
.sga-doc-panel-header{padding:10px 12px;background:#f2f7fd;border-bottom:1px solid #dce7f4}
.sga-doc-panel-header h3{margin:0 0 3px;color:#163d6c;font-size:14px}
.sga-doc-panel-header p{margin:0;color:#5f738a;font-size:11px;line-height:1.4}
.sga-doc-panel-body{padding:10px}
.sga-doc-panel-body label{font-size:12px;font-weight:700;color:#294d73}
.sga-doc-panel-body input[type=search]{margin-top:4px;width:100%;min-height:39px}
.sga-doc-personas{margin-top:8px;border:1px solid #e2e9f1;border-radius:9px;overflow-y:auto;max-height:min(42dvh,320px)}
.sga-doc-persona{width:100%;text-align:left;display:flex;align-items:center;justify-content:space-between;gap:7px;border:0;border-bottom:1px solid #edf1f6;background:#fff;color:#1c3854;cursor:pointer;padding:9px 10px;font:inherit;min-height:47px}
.sga-doc-persona:last-child{border-bottom:0}
.sga-doc-persona:hover{background:#eff6fd}
.sga-doc-persona[aria-pressed=true]{background:#e7f2ff;box-shadow:inset 4px 0 #1b69b1}
.sga-doc-persona strong{display:block;font-size:12px;line-height:1.4}
.sga-doc-persona small{display:block;color:#60768d;font-size:11px;margin-top:3px}
.sga-doc-persona .sga-doc-num{flex:0 0 auto;font-size:11px;background:#edf2fa;color:#2d537c;border-radius:16px;padding:4px 7px}
.sga-doc-vacio{color:#697e93;text-align:center;font-size:12px;padding:16px}
.sga-doc-seleccionado{background:#eef7ff;border:1px solid #cfe2f6;color:#244e75;border-radius:9px;margin:0 0 9px;padding:8px 10px}
.sga-doc-seleccionado strong{display:block;color:#154779;margin-top:2px;font-size:13px}
.sga-doc-seleccionado small{color:#637d94}
.sga-doc-asignaturas-controles{display:grid;grid-template-columns:minmax(145px,1fr) minmax(130px,170px);gap:8px;align-items:end}
.sga-doc-asignaturas-controles label{font-size:12px;font-weight:700;color:#335372}
.sga-doc-asignaturas-controles input,.sga-doc-asignaturas-controles select{width:100%;min-height:38px;margin-top:4px}
.sga-doc-lista-checks{margin-top:8px;display:flex;flex-direction:column;max-height:min(42dvh,320px);overflow:auto;border:1px solid #e0e8f2;border-radius:9px}
.sga-doc-materia-fila{display:flex!important;flex-direction:row!important;align-items:center!important;gap:10px;padding:9px 10px;border-bottom:1px solid #eaf0f6;cursor:pointer;margin:0!important}
.sga-doc-materia-fila:last-child{border-bottom:0}
.sga-doc-materia-fila:nth-child(even){background:#fbfdff}
.sga-doc-materia-fila:hover{background:#f5f9ff}
.sga-doc-materia-fila[hidden]{display:none!important}
.sga-doc-materia-fila[data-modificado="1"]{background:#eaf5ff;box-shadow:inset 4px 0 #2376b6}
.sga-doc-materia-fila[data-sga-objetivo="1"]{outline:2px solid #438bd0;outline-offset:-2px}
.sga-doc-materia-fila input[type=checkbox]{width:18px!important;height:18px!important;flex:0 0 18px;margin:0!important;padding:0!important;accent-color:#1469ad}
.sga-doc-materia-fila .sga-doc-materia-detalle{flex:1;min-width:0}
.sga-doc-materia-fila strong{display:block;font-size:12px;line-height:1.35;color:#173a60}
.sga-doc-materia-fila small{display:block;margin-top:2px;color:#657d96;font-size:11px;line-height:1.3}
.sga-doc-materia-fila .sga-doc-badge{display:inline-block;font-size:10px;font-weight:700;margin-top:4px;padding:2px 6px;border-radius:6px;background:#eef3f8;color:#49647d}
.sga-doc-materia-fila .sga-doc-badge.propia{background:#d9f3e3;color:#176139}
.sga-doc-materia-fila .sga-doc-badge.ajena{background:#fff1d8;color:#855916}
.sga-doc-materia-fila .sga-doc-accion{font-size:11px;display:block;color:#0967a8;margin-top:3px;font-weight:700}
.sga-doc-ayuda{padding:8px 10px;background:#fffbf2;border:1px solid #f1dfb3;border-radius:8px;color:#755d2d;font-size:11px;line-height:1.4;margin:8px 0 0}
.sga-doc-resumen{font-size:13px;font-weight:700;color:#1e567d}
.sga-doc-acciones-finales{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap;border-top:1px solid #e2eaf4;padding-top:10px;margin-top:12px}
.sga-doc-acciones-finales .sga-aula-modal-footer{margin:0}
@media(max-width:760px){.sga-doc-columnas{grid-template-columns:1fr}.sga-doc-personas{max-height:150px}.sga-doc-lista-checks{max-height:34dvh}}
/* Los dos dialogos priorizan las listas; el encabezado no consume tanto alto. */
#sga-modal-docente-individual .sga-aula-modal-header,#sga-modal-docentes .sga-aula-modal-header{position:sticky;top:0;z-index:3;background:#fff;padding:14px 18px}
#sga-modal-docente-individual .sga-aula-modal-header h2,#sga-modal-docentes .sga-aula-modal-header h2{font-size:19px}
#sga-modal-docente-individual .sga-aula-modal-header p,#sga-modal-docentes .sga-aula-modal-header p{font-size:12px;margin:3px 0 0}
#sga-modal-docente-individual .sga-aula-modal-body,#sga-modal-docentes .sga-aula-modal-body{padding:14px 18px 16px}
#sga-modal-docente-individual .sga-aula-modal-footer{margin-top:10px}
#sga-modal-docentes .sga-aula-modal-footer{gap:7px}
#sga-modal-docentes .sga-doc-acciones-finales{position:sticky;bottom:-16px;z-index:2;background:#fff;padding-bottom:5px;box-shadow:0 -5px 12px rgba(255,255,255,.94)}
@media(max-width:530px){.sga-doc-asignaturas-controles{grid-template-columns:1fr}.sga-doc-acciones-finales .sga-aula-modal-footer{width:100%;justify-content:flex-end}#sga-modal-docente-individual .sga-aula-modal-header,#sga-modal-docentes .sga-aula-modal-header{padding:12px 14px}#sga-modal-docente-individual .sga-aula-modal-body,#sga-modal-docentes .sga-aula-modal-body{padding:12px 14px}#sga-modal-docentes .sga-doc-acciones-finales{bottom:-12px}#sga-modal-docentes .sga-doc-acciones-finales .btn{padding:8px 9px;font-size:12px}}

@media(max-width:620px){.sga-aula-modal-header{padding:15px}.sga-aula-modal-body{padding:15px}.sga-aula-tabs{padding:0 15px}.sga-aula-tab{padding:13px 11px}.sga-aula-modal-footer .btn{flex:1 1 auto}.sga-aula-gestion-botones{flex-direction:column}.sga-aula-gestion-botones .btn{width:100%}}
</style>

<!-- Un solo flotante de matriculas: individual y masiva en pestañas. -->
<dialog class="sga-aula-modal" id="sga-modal-matricula" aria-labelledby="sga-titulo-matricula">
 <header class="sga-aula-modal-header"><div><h2 id="sga-titulo-matricula">Matricular estudiantes</h2><p>Selecciona la modalidad de matrícula para <?=e($ap['aula'].' '.$ap['paralelo'])?>.</p></div><button type="button" class="sga-aula-modal-close" data-sga-close aria-label="Cerrar ventana">&times;</button></header>
 <div class="sga-aula-tabs" role="tablist" aria-label="Tipo de matrícula">
  <button type="button" class="sga-aula-tab" id="sga-tab-individual" role="tab" aria-controls="sga-panel-individual" aria-selected="true" tabindex="0" data-sga-tab="sga-panel-individual">Individual</button>
  <button type="button" class="sga-aula-tab" id="sga-tab-masiva" role="tab" aria-controls="sga-panel-masiva" aria-selected="false" tabindex="-1" data-sga-tab="sga-panel-masiva">Masiva por CSV</button>
 </div>
 <section id="sga-panel-individual" class="sga-aula-modal-body sga-aula-tab-panel" role="tabpanel" aria-labelledby="sga-tab-individual">
  <p class="sga-aula-ayuda">Busca por cédula, nombres o apellidos y marca los estudiantes que deseas matricular. Los retirados de este mismo paralelo pueden reactivarse.</p>
  <?php if(!$disponibles):?><p class="sga-aula-resumen">No hay estudiantes disponibles para matricular en este período.</p><?php else:?>
  <form method="post" id="sga-form-matricula-individual">
   <input type="hidden" name="csrf_aula_gestion" value="<?=e($csrfAulaGestion)?>">
   <input type="hidden" name="accion" value="matricular"><input type="hidden" name="aula_periodo_id" value="<?=$apId?>">
   <label for="buscar-estudiante">Buscar estudiante<input id="buscar-estudiante" class="sga-aula-input-buscar" type="search" placeholder="Cédula, apellido o nombre..." autocomplete="off"></label>
   <div style="display:flex;justify-content:space-between;gap:8px;align-items:center;margin-top:10px"><span class="sga-aula-estadisticas" id="sga-cantidad-matriculas">0 seleccionados</span><span class="sga-aula-estadisticas"><?=count($disponibles)?> disponibles</span></div>
   <div class="sga-aula-lista" id="lista-disponibles">
    <?php foreach($disponibles as $u):$txt=$u['cedula'].' '.$u['apellidos'].' '.$u['nombres'];?><label class="sga-aula-fila fila-estudiante" data-search="<?=e($txt)?>"><input type="checkbox" name="usuarios[]" value="<?=(int)$u['id']?>" <?=$soloLectura?'disabled':''?>><span><strong><?=e($u['apellidos'].' '.$u['nombres'])?></strong><small><?=e($u['cedula'])?><?php if(($u['estado_previo']??'')==='retirado'):?> · Retirado: se reactivará<?php endif;?></small></span></label><?php endforeach;?>
    <div id="sin-resultados" class="sga-aula-resumen" hidden>No se encontraron estudiantes.</div>
   </div>
   <div class="sga-aula-modal-footer"><button class="btn btn-secondary" type="button" data-sga-close>Cancelar</button><button class="btn btn-primary" type="submit" <?=$soloLectura?'disabled':''?>>Matricular seleccionados</button></div>
  </form><?php endif;?>
 </section>
 <section id="sga-panel-masiva" class="sga-aula-modal-body sga-aula-tab-panel" role="tabpanel" aria-labelledby="sga-tab-masiva" hidden>
  <div class="sga-aula-descarga"><p>Descarga la plantilla CSV de este paralelo, completa las cédulas y súbela para matricular de forma masiva.</p><a class="btn btn-secondary" href="<?=e(url('modulos/academico/plantilla_matricula.php?aula_periodo_id='.$apId))?>">Descargar plantilla CSV</a></div>
  <form method="post" enctype="multipart/form-data" action="<?=e(url('modulos/academico/matricula_importar.php'))?>">
   <input type="hidden" name="csrf_aula_gestion" value="<?=e($csrfAulaGestion)?>">
   <input type="hidden" name="aula_periodo_id" value="<?=$apId?>">
   <label for="sga-archivo-matricula">Archivo CSV<input type="file" id="sga-archivo-matricula" name="archivo" accept=".csv,text/csv" required <?=$soloLectura?'disabled':''?>></label>
   <p class="sga-aula-ayuda">Tamaño máximo: 2 MB. La plantilla debe corresponder a esta aula.</p>
   <div class="sga-aula-modal-footer"><button class="btn btn-secondary" type="button" data-sga-close>Cancelar</button><button class="btn btn-primary" type="submit" <?=$soloLectura?'disabled':''?>>Importar matrículas</button></div>
  </form>
 </section>
</dialog>

<?php if(!$modoParametros):?>
<!-- Flotante 2: elegir materias aunque aun no haya profesor. -->
<dialog class="sga-aula-modal" id="sga-modal-asignaturas" aria-labelledby="sga-titulo-asignaturas">
 <header class="sga-aula-modal-header"><div><h2 id="sga-titulo-asignaturas">Seleccionar asignaturas del aula</h2><p>Marca las asignaturas que tendrá este paralelo. Puedes asignar sus docentes después.</p></div><button type="button" class="sga-aula-modal-close" data-sga-close aria-label="Cerrar ventana">&times;</button></header>
 <div class="sga-aula-modal-body">
  <form method="post" id="sga-form-asignaturas">
   <input type="hidden" name="csrf_aula_gestion" value="<?=e($csrfAulaGestion)?>"><input type="hidden" name="aula_periodo_id" value="<?=$apId?>"><input type="hidden" name="accion" value="guardar_asignaturas">
   <label for="sga-buscar-asignaturas">Buscar asignatura<input type="search" class="sga-aula-input-buscar" id="sga-buscar-asignaturas" placeholder="Nombre, código o área..."></label>
   <label class="sga-aula-select-todo"><input id="sga-check-todas-asignaturas" type="checkbox" <?=$soloLectura?'disabled':''?>>Seleccionar todas las asignaturas</label>
   <div class="sga-aula-estadisticas" id="sga-cantidad-asignaturas" style="margin-top:8px"><?=count($seleccionadasAula)?> de <?=count($asigs)?> seleccionadas</div>
   <div class="sga-aula-lista" id="sga-lista-asignaturas">
    <?php foreach($asigs as $a):$idMateria=(int)$a['id'];$nombreAsig=($a['codigo']?$a['codigo'].' · ':'').$a['nombre'];$buscarAsig=$a['codigo'].' '.$a['nombre'].' '.$a['area'];?><label class="sga-aula-fila sga-aula-fila-asig" data-search="<?=e($buscarAsig)?>"><input type="checkbox" class="sga-aula-check-asig" name="asignaturas[]" value="<?=$idMateria?>" <?=isset($seleccionadasIds[$idMateria])?'checked':''?> <?=$soloLectura?'disabled':''?>><span><strong><?=e($nombreAsig)?></strong><small><?=e($a['area'])?></small></span></label><?php endforeach;?>
   </div>
   <p class="sga-aula-ayuda">Si desmarcas una asignatura con docente, su oferta se desactivará. Las calificaciones y asistencias anteriores se conservarán.</p>
   <div class="sga-aula-modal-footer"><button class="btn btn-secondary" type="button" data-sga-close>Cancelar</button><button class="btn btn-primary" type="submit" <?=$soloLectura?'disabled':''?>>Guardar asignaturas</button></div>
  </form>
 </div>
</dialog>

<!-- Ventana independiente para el botón de UNA fila: no muestra casillas de materias. -->
<dialog class="sga-aula-modal" id="sga-modal-docente-individual" aria-labelledby="sga-simple-titulo" aria-describedby="sga-simple-descripcion">
 <header class="sga-aula-modal-header">
  <div><h2 id="sga-simple-titulo">Asignar docente</h2><p id="sga-simple-descripcion">Busca y elige un docente para esta materia.</p></div>
  <button type="button" class="sga-aula-modal-close" data-sga-close aria-label="Cerrar ventana">&times;</button>
 </header>
 <div class="sga-aula-modal-body">
  <div class="sga-doc-ind-materia" role="status">
   <span class="sga-doc-ind-etiqueta">Asignatura</span>
   <strong id="sga-simple-asignatura">—</strong>
   <small id="sga-simple-area"></small>
   <span class="sga-doc-ind-actual" id="sga-simple-actual"></span>
  </div>
  <form method="post" id="sga-form-docente-individual">
   <input type="hidden" name="csrf_aula_gestion" value="<?=e($csrfAulaGestion)?>">
   <input type="hidden" name="accion" value="oferta_individual">
   <input type="hidden" name="aula_periodo_id" value="<?=$apId?>">
   <input type="hidden" name="asignatura_id" id="sga-simple-id-asignatura" value="">
   <input type="hidden" name="version_oferta" id="sga-simple-version" value="">
   <label for="sga-simple-buscar"><strong>Buscar docente</strong></label>
   <input type="search" id="sga-simple-buscar" placeholder="Nombre, apellido o cédula..." autocomplete="off" aria-controls="sga-simple-lista">
   <div id="sga-simple-lista" class="sga-doc-ind-opciones" role="group" aria-label="Docentes disponibles">
    <label class="sga-doc-ind-opcion sga-doc-ind-sin-docente" data-sga-sin-docente="1" data-search="sin docente sin asignar">
     <input type="radio" name="docente_id" value="0" required <?=$soloLectura?'disabled':''?>>
     <span><strong>Sin docente</strong><small>Dejar esta asignatura sin responsable</small></span>
    </label>
    <?php foreach($personas as $docenteIndividual):
       $nombreIndividual=trim($docenteIndividual['apellidos'].' '.$docenteIndividual['nombres']); ?>
    <label class="sga-doc-ind-opcion" data-search="<?=e($nombreIndividual.' '.$docenteIndividual['cedula'])?>">
     <input type="radio" name="docente_id" value="<?=(int)$docenteIndividual['id']?>" required <?=$soloLectura?'disabled':''?>>
     <span><strong><?=e($nombreIndividual)?></strong><small>Cédula: <?=e($docenteIndividual['cedula'])?></small></span>
    </label>
    <?php endforeach;?>
    <div class="sga-doc-ind-vacio" id="sga-simple-sin-resultados" hidden>No se encontraron docentes con ese nombre o cédula.</div>
   </div>
   <p class="sga-doc-ind-resultado" id="sga-simple-resumen" role="status" aria-live="polite">Selecciona un docente para continuar.</p>
   <div class="sga-aula-modal-footer">
    <button type="button" class="btn btn-secondary" data-sga-close>Cancelar</button>
    <button class="btn btn-primary" id="sga-simple-guardar" type="submit" disabled>Asignar docente</button>
   </div>
  </form>
 </div>
</dialog>

<!-- Flotante 3: elegir UN docente; ver sus asignaturas con checks. -->
<dialog class="sga-aula-modal" id="sga-modal-docentes" aria-labelledby="sga-titulo-docentes" aria-describedby="sga-descripcion-docentes">
 <header class="sga-aula-modal-header">
  <div><h2 id="sga-titulo-docentes">Asignar docentes</h2><p id="sga-descripcion-docentes">Elige un docente y marca sus asignaturas en <?=e($ap['aula'].' '.$ap['paralelo'])?>.</p></div>
  <button type="button" class="sga-aula-modal-close" data-sga-close aria-label="Cerrar ventana">&times;</button>
 </header>
 <div class="sga-aula-modal-body">
 <?php if(!$seleccionadasAula):?>
  <p class="sga-aula-resumen">Esta aula aún no tiene asignaturas seleccionadas. Primero elige las materias del paralelo.</p>
  <div class="sga-aula-modal-footer"><button type="button" class="btn btn-primary" data-sga-goto="sga-modal-asignaturas">Seleccionar asignaturas</button></div>
 <?php elseif(!$personas):?>
  <p class="sga-aula-resumen">No hay docentes disponibles para la jornada de esta aula. Revisa las jornadas y roles asignados.</p>
 <?php else:?>
  <?php
    $asignacionesPorDocente=[];
    foreach($seleccionadasAula as $materiaParaContar){
      $ofertaParaContar=$ofertasPorAsignatura[(int)$materiaParaContar['id']]??null;
      if($ofertaParaContar && (int)$ofertaParaContar['activo']===1){
        $idContar=(int)$ofertaParaContar['docente_id'];
        $asignacionesPorDocente[$idContar]=($asignacionesPorDocente[$idContar]??0)+1;
      }
    }
  ?>
 <form method="post" id="sga-form-docentes">
  <input type="hidden" name="csrf_aula_gestion" value="<?=e($csrfAulaGestion)?>">
  <input type="hidden" name="aula_periodo_id" value="<?=$apId?>">
  <input type="hidden" name="accion" value="guardar_docentes">
  <input type="hidden" name="docente_id" id="sga-docente-seleccionado-id" value="">
  <div class="sga-doc-columnas">
   <section class="sga-doc-panel" aria-labelledby="sga-docentes-personas-titulo">
    <div class="sga-doc-panel-header"><h3 id="sga-docentes-personas-titulo">1. Elegir docente</h3><p>Docentes de la jornada del aula.</p></div>
    <div class="sga-doc-panel-body">
     <label for="sga-buscar-docente">Buscar docente</label>
     <input class="sga-aula-input-buscar" type="search" id="sga-buscar-docente" autocomplete="off" placeholder="Nombre, apellido o cédula...">
     <div class="sga-doc-personas" id="sga-doc-lista-personas" aria-label="Resultados de docentes">
      <?php foreach($personas as $docente):
       $docId=(int)$docente['id'];
       $nombreDocente=trim($docente['apellidos'].' '.$docente['nombres']);
       $cantidad=(int)($asignacionesPorDocente[$docId]??0);
      ?>
       <button type="button" class="sga-doc-persona" data-docente-id="<?=$docId?>" data-docente-nombre="<?=e($nombreDocente)?>" data-search="<?=e($nombreDocente.' '.$docente['cedula'])?>" aria-pressed="false">
        <span><strong><?=e($nombreDocente)?></strong><small>Cédula: <?=e($docente['cedula'])?></small></span>
        <span class="sga-doc-num"><?=$cantidad?> materia<?=$cantidad===1?'':'s'?></span>
       </button>
      <?php endforeach;?>
     </div>
     <div id="sga-doc-sin-personas" class="sga-doc-vacio" hidden>No hay docentes que coincidan con la búsqueda.</div>
    </div>
   </section>
   <section class="sga-doc-panel" aria-labelledby="sga-docentes-materias-titulo">
    <div class="sga-doc-panel-header"><h3 id="sga-docentes-materias-titulo">2. Marcar asignaturas</h3><p>Las marcadas ya pertenecen al docente.</p></div>
    <div class="sga-doc-panel-body">
     <div class="sga-aula-resumen" id="sga-doc-sin-elegir">Elige un docente para ver y marcar sus asignaturas.</div>
     <div id="sga-doc-asignaturas-panel" hidden>
      <div class="sga-doc-seleccionado"><small>Docente seleccionado</small><strong id="sga-doc-nombre-elegido"></strong><small id="sga-doc-total-actual"></small></div>
      <div class="sga-doc-asignaturas-controles">
       <label for="sga-buscar-materia-docente">Buscar materia
        <input type="search" id="sga-buscar-materia-docente" placeholder="Asignatura o área..." autocomplete="off">
       </label>
       <label for="sga-filtro-materias-docente">Mostrar
        <select id="sga-filtro-materias-docente">
         <option value="todas">Todas las asignaturas</option>
         <option value="propias">Asignadas a este docente</option>
         <option value="libres">Sin docente</option>
         <option value="ajenas">Asignadas a otro docente</option>
         <option value="cambios">Cambios pendientes</option>
        </select>
       </label>
      </div>
      <div class="sga-doc-lista-checks" id="sga-lista-materias-docentes">
       <?php foreach($seleccionadasAula as $materia):
         $materiaId=(int)$materia['id'];
         $ofertaActual=$ofertasPorAsignatura[$materiaId]??null;
         $asignada=$ofertaActual&&(int)$ofertaActual['activo']===1;
         $actualId=$asignada?(int)$ofertaActual['docente_id']:0;
         $actualNombre=$asignada?(string)$ofertaActual['docente']:'';
         $nombreMateria=($materia['codigo']?$materia['codigo'].' · ':'').$materia['nombre'];
       ?>
       <label class="sga-doc-materia-fila" data-asignatura="<?=$materiaId?>" data-dueno="<?=$actualId?>" data-docente-actual="<?=e($actualNombre)?>" data-search="<?=e($nombreMateria.' '.$materia['area'])?>" data-modificado="0">
        <input type="hidden" name="docentes_originales[<?=$materiaId?>]" value="<?=$actualId?>">
        <input type="checkbox" class="sga-doc-check-materia" name="asignaturas_docente[]" value="<?=$materiaId?>" <?=$soloLectura?'disabled':''?> >
        <span class="sga-doc-materia-detalle"><strong><?=e($nombreMateria)?></strong><small><?=e($materia['area'])?></small><span class="sga-doc-badge"></span><span class="sga-doc-accion"></span></span>
       </label>
       <?php endforeach;?>
      </div>
      <p id="sga-sin-materias-docentes" class="sga-doc-vacio" hidden>No hay asignaturas que coincidan con este filtro.</p>
      <p class="sga-doc-ayuda">Marcar asigna y desmarcar retira. Si tiene otro docente, se cambiará el responsable al guardar.</p>
     </div>
    </div>
   </section>
  </div>
  <div class="sga-doc-acciones-finales">
   <div class="sga-doc-resumen" id="sga-resumen-docentes" role="status" aria-live="polite">Selecciona un docente para comenzar.</div>
   <div class="sga-aula-modal-footer">
    <button class="btn btn-secondary" type="button" id="sga-restablecer-docentes" disabled>Deshacer cambios</button>
    <button class="btn btn-secondary" type="button" data-sga-close>Cancelar</button>
    <button class="btn btn-primary" type="submit" id="sga-guardar-docentes" disabled>Guardar asignaciones</button>
   </div>
  </div>
 </form>
 <?php endif;?>
 </div>
</dialog>

<?php endif;?>
<script>
(function () {
  'use strict';
  var dialogs=[...document.querySelectorAll('.sga-aula-modal')];
  function abrir(id, elemento){
    var d=document.getElementById(id);
    if(!d || typeof d.showModal!=='function')return;
    if(elemento)d._sgaOrigen=elemento;
    if(!d.open)d.showModal();
  }
  document.addEventListener('click',function(e){var b=e.target.closest('[data-sga-open]');if(b)abrir(b.dataset.sgaOpen,b);});
  dialogs.forEach(function(d){
    d.querySelectorAll('[data-sga-close]').forEach(function(b){b.addEventListener('click',function(){d.close();});});
    d.addEventListener('click',function(ev){if(ev.target!==d)return;var r=d.getBoundingClientRect();if(ev.clientX<r.left||ev.clientX>r.right||ev.clientY<r.top||ev.clientY>r.bottom)d.close();});
    d.addEventListener('close',function(){if(d._sgaOrigen && document.contains(d._sgaOrigen))d._sgaOrigen.focus({preventScroll:true});});
  });
  document.querySelectorAll('[data-sga-goto]').forEach(function(b){b.addEventListener('click',function(){var actual=b.closest('dialog');if(actual)actual.close();abrir(b.dataset.sgaGoto,b);});});
  var dlgMat=document.getElementById('sga-modal-matricula');
  if(dlgMat){
    var tabs=[...dlgMat.querySelectorAll('[data-sga-tab]')];
    function activarTab(tab){tabs.forEach(function(t){var activo=t===tab;t.setAttribute('aria-selected',activo?'true':'false');t.tabIndex=activo?0:-1;var panel=document.getElementById(t.dataset.sgaTab);if(panel)panel.hidden=!activo;});}
    tabs.forEach(function(t){t.addEventListener('click',function(){activarTab(t);});t.addEventListener('keydown',function(e){if(e.key!=='ArrowRight'&&e.key!=='ArrowLeft')return;e.preventDefault();var n=tabs.indexOf(t),proximo=tabs[(n+(e.key==='ArrowRight'?1:tabs.length-1))%tabs.length];activarTab(proximo);proximo.focus();});});
  }
  function normalizar(s){return (s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();}
  function buscarLista(inputId,itemSelector,emptyId){
    var input=document.getElementById(inputId);if(!input)return;
    var items=[...document.querySelectorAll(itemSelector)];
    var vacio=emptyId?document.getElementById(emptyId):null;
    input.addEventListener('input',function(){var q=normalizar(input.value),visibles=0;items.forEach(function(row){var ok=!q||normalizar(row.dataset.search).includes(q);row.hidden=!ok;row.style.display=ok?'':'none';if(ok)visibles++;});if(vacio)vacio.hidden=visibles>0;});
  }
  buscarLista('buscar-estudiante','#lista-disponibles .fila-estudiante','sin-resultados');
  buscarLista('sga-buscar-asignaturas','#sga-lista-asignaturas .sga-aula-fila-asig');
  // Botón de cada fila: ventana pequeña de elección única, sin tocar el editor masivo.
  var simpleDialog=document.getElementById('sga-modal-docente-individual');
  var simpleForm=document.getElementById('sga-form-docente-individual');
  function abrirDocenteIndividual(boton){
    if(!simpleDialog || !boton)return;
    document.getElementById('sga-simple-asignatura').textContent=boton.dataset.sgaSimpleAsignatura||'';
    document.getElementById('sga-simple-area').textContent=boton.dataset.sgaSimpleArea||'';
    var actual=boton.dataset.sgaSimpleActual||'';
    var estado=boton.dataset.sgaSimpleEstado||'sin';
    document.getElementById('sga-simple-actual').textContent=estado==='activa'?'Docente actual: '+actual:(estado==='inactiva'?'Actualmente sin docente'+(actual?' (último responsable: '+actual+')':''):'Pendiente de docente');
    if(simpleForm){
      simpleForm.reset();
      document.getElementById('sga-simple-id-asignatura').value=boton.dataset.sgaSimpleId||'';
      document.getElementById('sga-simple-version').value=boton.dataset.sgaSimpleVersion||'';
      var buscador=document.getElementById('sga-simple-buscar');
      if(buscador)buscador.value='';
      simpleForm.querySelectorAll('.sga-doc-ind-opcion').forEach(function(op){op.hidden=false;});
      var vacio=document.getElementById('sga-simple-sin-resultados');if(vacio)vacio.hidden=true;
      document.getElementById('sga-simple-guardar').disabled=true;
      document.getElementById('sga-simple-guardar').textContent=estado==='activa'?'Guardar docente':'Asignar docente';
      document.getElementById('sga-simple-resumen').textContent='Selecciona un docente para continuar.';
    }
    abrir('sga-modal-docente-individual',boton);
    var campo=document.getElementById('sga-simple-buscar');
    if(campo)campo.focus({preventScroll:true});
  }
  document.addEventListener('click',function(evento){
    var boton=evento.target.closest('[data-sga-simple-id]');
    if(boton){evento.preventDefault();abrirDocenteIndividual(boton);}
  });
  if(simpleForm){
    var simpleBuscar=document.getElementById('sga-simple-buscar');
    var simpleOpciones=[...simpleForm.querySelectorAll('.sga-doc-ind-opcion')];
    var simpleGuardar=document.getElementById('sga-simple-guardar');
    var simpleResumen=document.getElementById('sga-simple-resumen');
    function actualizarDocenteIndividual(){
      var texto=normalizar(simpleBuscar.value),docentesVisibles=0;
      simpleOpciones.forEach(function(fila){
        // "Sin docente" siempre se conserva como primera opción, incluso al buscar.
        var sinDocente=fila.dataset.sgaSinDocente==='1';
        var coincide=sinDocente||!texto||normalizar(fila.dataset.search).includes(texto);
        fila.hidden=!coincide;
        if(coincide&&!sinDocente)docentesVisibles++;
        else if(!coincide)fila.querySelector('input[type=radio]').checked=false;
      });
      document.getElementById('sga-simple-sin-resultados').hidden=docentesVisibles>0;
      var seleccionado=simpleForm.querySelector('input[name="docente_id"]:checked');
      simpleGuardar.disabled=<?=json_encode($soloLectura)?>||!seleccionado;
      var seleccionadoNombre=seleccionado?seleccionado.closest('label').querySelector('strong').textContent:'';
      simpleGuardar.textContent=seleccionado&&seleccionado.value==='0'?'Dejar sin docente':(document.getElementById('sga-simple-actual').textContent.startsWith('Docente actual:')?'Guardar docente':'Asignar docente');
      simpleResumen.textContent=seleccionado?'Seleccionado: '+seleccionadoNombre:'Selecciona un docente para continuar.';
    }
    simpleBuscar.addEventListener('input',actualizarDocenteIndividual);
    simpleForm.addEventListener('change',actualizarDocenteIndividual);
    simpleForm.addEventListener('submit',function(evento){
      if(!simpleForm.querySelector('input[name="docente_id"]:checked')){evento.preventDefault();return;}
      var seleccionado=simpleForm.querySelector('input[name="docente_id"]:checked');
      var datos=seleccionado.closest('label').querySelector('strong').textContent;
      var asignatura=document.getElementById('sga-simple-asignatura').textContent;
      var actual=document.getElementById('sga-simple-actual').textContent;
      if(seleccionado.value==='0' && actual.startsWith('Docente actual:')){
        if(!window.confirm('¿Dejar '+asignatura+' sin docente? Se conservarán las notas y asistencias anteriores.'))evento.preventDefault();
      }else if(seleccionado.value!=='0' && actual.startsWith('Docente actual:') && !window.confirm('¿Cambiar el docente de '+asignatura+' por '+datos+'?'))evento.preventDefault();
    });
  }
  // Enlaces anteriores ?editar_oferta=... también abren la ventana individual.
  var ofertaDesdeURL=<?=json_encode($editarOferta?(int)$editarOferta['asignatura_id']:0)?>;
  if(ofertaDesdeURL){
    var abrirAnterior=function(){var b=document.querySelector('[data-sga-simple-id="'+ofertaDesdeURL+'"]');if(b)abrirDocenteIndividual(b);};
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',abrirAnterior,{once:true});
    else abrirAnterior();
  }
  var formDocentes=document.getElementById('sga-form-docentes');
  if(formDocentes){
    var botonesDocentes=[...formDocentes.querySelectorAll('.sga-doc-persona')];
    var filasDocentes=[...formDocentes.querySelectorAll('.sga-doc-materia-fila')];
    var buscarDocente=document.getElementById('sga-buscar-docente');
    var buscarMateriaDoc=document.getElementById('sga-buscar-materia-docente');
    var filtrarMateriasDoc=document.getElementById('sga-filtro-materias-docente');
    var seleccionadoId=document.getElementById('sga-docente-seleccionado-id');
    var seleccionPanel=document.getElementById('sga-doc-asignaturas-panel');
    var faltaElegir=document.getElementById('sga-doc-sin-elegir');
    var seleccionadoNombre=document.getElementById('sga-doc-nombre-elegido');
    var seleccionadoTotal=document.getElementById('sga-doc-total-actual');
    var resumenDocentes=document.getElementById('sga-resumen-docentes');
    var botonGuardarDocentes=document.getElementById('sga-guardar-docentes');
    var botonRestablecerDocentes=document.getElementById('sga-restablecer-docentes');
    var sinResultadosDocentes=document.getElementById('sga-sin-materias-docentes');
    var sinPersonas=document.getElementById('sga-doc-sin-personas');
    var lecturaDocentes=<?=json_encode($soloLectura)?>;
    var docenteActual=0,modificadasActual=0,materiaDestacada=0;
    function esOriginal(fila){return Number(fila.dataset.dueno)===docenteActual;}
    function buscarPersonas(){
      var consulta=normalizar(buscarDocente.value),cantidad=0;
      botonesDocentes.forEach(function(b){var ok=!consulta||normalizar(b.dataset.search).includes(consulta);b.hidden=!ok;b.style.display=ok?'':'none';if(ok)cantidad++;});
      if(sinPersonas)sinPersonas.hidden=cantidad>0;
    }
    function refrescarMaterias(){
      if(!docenteActual)return;
      var modificadas=0,retiradas=0,transferidas=0,marcadas=0,visibles=0,actuales=0;
      var texto=normalizar(buscarMateriaDoc.value);
      var filtro=filtrarMateriasDoc.value;
      filasDocentes.forEach(function(fila){
        var check=fila.querySelector('.sga-doc-check-materia');
        var dueño=Number(fila.dataset.dueno);
        var antes=dueño===docenteActual;
        var ahora=check.checked;
        var cambió=antes!==ahora;
        var badge=fila.querySelector('.sga-doc-badge');
        var accion=fila.querySelector('.sga-doc-accion');
        if(antes)actuales++;
        if(ahora)marcadas++;
        if(cambió){
          modificadas++;
          if(!ahora)retiradas++;
          else if(dueño>0 && dueño!==docenteActual)transferidas++;
        }
        fila.dataset.modificado=cambió?'1':'0';
        if(antes){badge.textContent='Ya asignada a este docente';badge.className='sga-doc-badge propia';}
        else if(dueño>0){badge.textContent='Asignada a: '+fila.dataset.docenteActual;badge.className='sga-doc-badge ajena';}
        else{badge.textContent='Sin docente';badge.className='sga-doc-badge';}
        accion.textContent=cambió?(ahora?(dueño>0?'Se transferirá al guardar':'Se asignará al guardar'):'Se retirará al guardar'):'';
        var coincide=!texto||normalizar(fila.dataset.search).includes(texto);
        var coincideFiltro=filtro==='todas'||(filtro==='propias'&&antes)||(filtro==='libres'&&dueño===0)||(filtro==='ajenas'&&dueño>0&&!antes)||(filtro==='cambios'&&cambió);
        fila.hidden=!(coincide&&coincideFiltro);
        fila.style.order=antes?'0':dueño===0?'1':'2';
        if(!fila.hidden)visibles++;
      });
      if(seleccionadoTotal)seleccionadoTotal.textContent=actuales+' asignatura'+(actuales===1?'':'s')+' actual'+(actuales===1?'':'es');
      if(sinResultadosDocentes)sinResultadosDocentes.hidden=visibles>0;
      if(resumenDocentes)resumenDocentes.textContent=marcadas+' materia'+(marcadas===1?'':'s')+' marcada'+(marcadas===1?'':'s')+' · '+modificadas+' cambio'+(modificadas===1?'':'s')+' pendiente'+(modificadas===1?'':'s');
      if(botonGuardarDocentes){botonGuardarDocentes.disabled=lecturaDocentes||modificadas===0;botonGuardarDocentes.textContent='Guardar cambios ('+modificadas+')';}
      if(botonRestablecerDocentes)botonRestablecerDocentes.disabled=lecturaDocentes||modificadas===0;
      modificadasActual=modificadas;
      formDocentes.dataset.retiradas=String(retiradas);
      formDocentes.dataset.transferidas=String(transferidas);
    }
    function elegirDocente(boton){
      var nuevo=Number(boton.dataset.docenteId);
      if(nuevo===docenteActual)return true;
      if(modificadasActual>0&&!window.confirm('Tienes cambios sin guardar. ¿Cambiar de docente y descartarlos?'))return false;
      docenteActual=nuevo;
      seleccionadoId.value=String(nuevo);
      botonesDocentes.forEach(function(b){b.setAttribute('aria-pressed',b===boton?'true':'false');});
      seleccionadoNombre.textContent=boton.dataset.docenteNombre;
      faltaElegir.hidden=true;seleccionPanel.hidden=false;
      buscarMateriaDoc.value='';filtrarMateriasDoc.value='todas';
      filasDocentes.forEach(function(fila){
        var check=fila.querySelector('.sga-doc-check-materia');
        check.checked=esOriginal(fila);
        fila.dataset.sgaObjetivo=Number(fila.dataset.asignatura)===materiaDestacada?'1':'0';
      });
      refrescarMaterias();
      if(materiaDestacada){
        var objetivoVisible=filasDocentes.find(function(f){return Number(f.dataset.asignatura)===materiaDestacada;});
        if(objetivoVisible)objetivoVisible.scrollIntoView({block:'nearest'});
      }
      return true;
    }
    botonesDocentes.forEach(function(b){b.addEventListener('click',function(){elegirDocente(b);});});
    buscarDocente.addEventListener('input',buscarPersonas);
    buscarMateriaDoc.addEventListener('input',refrescarMaterias);
    filtrarMateriasDoc.addEventListener('change',refrescarMaterias);
    filasDocentes.forEach(function(f){f.querySelector('input[type=checkbox]').addEventListener('change',refrescarMaterias);});
    if(botonRestablecerDocentes)botonRestablecerDocentes.addEventListener('click',function(){
      filasDocentes.forEach(function(f){f.querySelector('input[type=checkbox]').checked=esOriginal(f);});
      refrescarMaterias();
    });
    formDocentes.addEventListener('submit',function(ev){
      if(!docenteActual||!modificadasActual){ev.preventDefault();return;}
      var transferencias=Number(formDocentes.dataset.transferidas||0);
      var retiradas=Number(formDocentes.dataset.retiradas||0);
      if(transferencias||retiradas){
        var mensaje='Se aplicarán '+modificadasActual+' cambio(s) a '+seleccionadoNombre.textContent+'.';
        if(transferencias)mensaje+='\n'+transferencias+' materia(s) pasarán desde otro docente.';
        if(retiradas)mensaje+='\n'+retiradas+' materia(s) se retirarán de este docente.';
        mensaje+='\nLas notas y asistencias históricas se conservarán. ¿Continuar?';
        if(!window.confirm(mensaje))ev.preventDefault();
      }
    });
    buscarPersonas();
  }
  var listaIndividual=document.getElementById('lista-disponibles'),contadorMat=document.getElementById('sga-cantidad-matriculas');
  if(listaIndividual&&contadorMat){
    function actualizarMat(){contadorMat.textContent=listaIndividual.querySelectorAll('input[name="usuarios[]"]:checked').length+' seleccionados';}
    listaIndividual.addEventListener('change',actualizarMat);actualizarMat();
  }
  var marcarTodas=document.getElementById('sga-check-todas-asignaturas');
  var checkAsigs=[...document.querySelectorAll('.sga-aula-check-asig')];
  var cantidadAsigs=document.getElementById('sga-cantidad-asignaturas');
  function actualizarAsigs(){if(!marcarTodas)return;var n=checkAsigs.filter(function(c){return c.checked;}).length;marcarTodas.checked=checkAsigs.length>0&&n===checkAsigs.length;marcarTodas.indeterminate=n>0&&n<checkAsigs.length;if(cantidadAsigs)cantidadAsigs.textContent=n+' de '+checkAsigs.length+' seleccionadas';}
  if(marcarTodas){marcarTodas.addEventListener('change',function(){checkAsigs.forEach(function(c){if(!c.disabled)c.checked=marcarTodas.checked;});actualizarAsigs();});checkAsigs.forEach(function(c){c.addEventListener('change',actualizarAsigs);});actualizarAsigs();}
  var formAsigs=document.getElementById('sga-form-asignaturas');
  if(formAsigs)formAsigs.addEventListener('submit',function(ev){if(checkAsigs.some(function(c){return c.checked;}))return;if(!window.confirm('Se deseleccionarán todas las asignaturas y se desactivarán sus ofertas académicas. Las notas y asistencias se conservan. ¿Continuar?'))ev.preventDefault();});

})();
</script>
<?php if($modoParametros): ?>
<section class="card" style="margin-bottom:16px">
 <div class="toolbar" style="align-items:center;gap:12px"><div><h2 class="section-title" style="margin:0 0 5px">Docente responsable del aula</h2><p class="muted" style="margin:0">Evaluación cualitativa por parámetros · Trimestres 1, 2 y 3</p></div><span class="badge good">Un único docente</span></div>
 <?php if($principalParametros && (int)$principalParametros['activo']): ?>
 <p><strong><?=e($principalParametros['docente'])?></strong> · Responsable de todos los ejes, ámbitos e indicadores.</p>
 <div class="actions" style="margin-bottom:14px">
 <a class="btn btn-primary" href="<?=e(url('modulos/calificaciones/parametros.php?oferta_id='.$principalParametros['id']))?>"><?=$soloLectura || !(int)$ap['activo']?'Consultar parámetros':'Calificar parámetros'?></a>
 <a class="btn btn-secondary" href="<?=e(url('modulos/calificaciones/parametros.php?oferta_id='.$principalParametros['id'].'&vista=resumen'))?>">Resumen T1–T3</a>
 <a class="btn btn-success" href="<?=e(url('modulos/asistencia/registro.php?oferta_id='.$principalParametros['id']))?>">Asistencia</a>
 <a class="btn btn-secondary" href="<?=e(url('modulos/academico/lista.php?oferta_id='.$principalParametros['id']))?>">Lista de estudiantes</a>
 </div>
 <?php else: ?><p class="alert info">Todavía no hay un docente responsable activo. Selecciónalo a continuación.</p><?php endif;?>
 <?php if(!$soloLectura && (int)$ap['activo']): ?>
 <form method="post" class="form-grid cols-2" style="align-items:end">
 <input type="hidden" name="csrf_aula_gestion" value="<?=e($csrfAulaGestion)?>"><input type="hidden" name="accion" value="asignar_docente_aula"><input type="hidden" name="aula_periodo_id" value="<?=$apId?>">
 <?php if(!$principalParametros && count($historialParametros)>1):?>
 <label>Registro anterior que será el principal<select name="origen_id" required><option value="">Seleccionar registro</option><?php foreach($historialParametros as $h):?><option value="<?=(int)$h['id']?>"><?=e($h['asignatura'].' · '.$h['valoraciones'].' valoraciones')?></option><?php endforeach;?></select><small class="muted">Los demás registros se conservarán en el historial, sin fusionar notas.</small></label>
 <?php endif;?>
 <label>Docente del aula<select name="docente_id" required><option value="">Seleccionar docente</option><?php foreach($personas as $d):?><option value="<?=(int)$d['id']?>" <?=($principalParametros && (int)$principalParametros['docente_id']===(int)$d['id'])?'selected':''?>><?=e($d['apellidos'].' '.$d['nombres'].' · '.$d['cedula'])?></option><?php endforeach;?></select></label>
 <button class="btn btn-primary" type="submit" <?=!$personas?'disabled':''?>><?=$principalParametros && (int)$principalParametros['activo']?'Actualizar docente':'Asignar docente'?></button>
 </form>
 <p class="mini-note">Cambiar el docente no elimina ni modifica las valoraciones ya guardadas. El docente responsable, el administrador y los subadministradores autorizados para esta jornada pueden calificar los tres trimestres.</p>
 <?php endif;?>
</section>
<?php else: ?>
<h2 class="section-title">Asignaturas del aula</h2>
<div class="table-wrap"><table class="table table-responsive-cards">
<thead><tr><th>Área</th><th>Asignatura</th><th>Docente</th><th>Estado</th><th>Gestión</th></tr></thead>
<tbody>
<?php if(!$ofertas && !$pendientesSinDocente):?><tr><td colspan="5" class="empty">Sin asignaturas asignadas.</td></tr><?php endif;?>
<?php foreach($pendientesSinDocente as $pendiente):
 $idPendiente=(int)$pendiente['id'];
 $pendienteOferta=$ofertasPorAsignatura[$idPendiente]??null;
 $versionPendiente=$pendienteOferta?((int)$pendienteOferta['id'].':'.(int)$pendienteOferta['activo'].':'.(int)$pendienteOferta['docente_id']):'0:0:0';
 $docenteAnterior=$pendienteOferta?(string)$pendienteOferta['docente']:'';
?>
<tr>
 <td><?=e($pendiente['area'])?></td>
 <td><strong><?=e($pendiente['nombre'])?></strong></td>
 <td>Sin asignar</td>
 <td><span class="badge warn">Pendiente de docente</span></td>
 <td><button type="button" class="btn btn-sm btn-primary"
    data-sga-simple-id="<?=$idPendiente?>"
    data-sga-simple-asignatura="<?=e($pendiente['nombre'])?>"
    data-sga-simple-area="<?=e($pendiente['area'])?>"
    data-sga-simple-actual="<?=e($docenteAnterior)?>"
    data-sga-simple-estado="<?=$pendienteOferta?'inactiva':'sin'?>"
    data-sga-simple-version="<?=e($versionPendiente)?>"
    aria-haspopup="dialog" aria-controls="sga-modal-docente-individual"
    <?=$soloLectura?'disabled':''?>>Asignar docente</button></td>
</tr>
<?php endforeach;?>
<?php foreach($ofertas as $o):
 if((int)$o['activo']!==1)continue; // Ya aparece una vez arriba como pendiente de docente.
 $versionOferta=(int)$o['id'].':'.(int)$o['activo'].':'.(int)$o['docente_id'];
?>
<tr>
 <td><?=e($o['area'])?></td>
 <td><strong><?=e($o['asignatura'])?></strong></td>
 <td><?=e($o['docente'])?></td>
 <td><span class="badge <?=$o['activo']?'good':'bad'?>"><?=$o['activo']?'Activa':'Inactiva'?></span></td>
 <td><div class="actions">
  <?php if($o['activo']):?>
   <a class="btn btn-sm btn-primary" href="<?=e(url('modulos/calificaciones/index.php?oferta_id='.$o['id']))?>">Calificaciones</a>
   <a class="btn btn-sm btn-success" href="<?=e(url('modulos/asistencia/registro.php?oferta_id='.$o['id']))?>">Asistencia</a>
   <a class="btn btn-sm btn-secondary" href="<?=e(url('modulos/academico/lista.php?oferta_id='.$o['id']))?>">Lista</a>
   <a class="btn btn-sm btn-secondary" href="<?=e(url('modulos/calificaciones/finales.php?oferta_id='.$o['id']))?>">Finales</a>
  <?php endif;?>
  <button type="button" class="btn btn-sm btn-secondary"
    data-sga-simple-id="<?=(int)$o['asignatura_id']?>"
    data-sga-simple-asignatura="<?=e($o['asignatura'])?>"
    data-sga-simple-area="<?=e($o['area'])?>"
    data-sga-simple-actual="<?=e($o['docente'])?>"
    data-sga-simple-estado="<?=$o['activo']?'activa':'inactiva'?>"
    data-sga-simple-version="<?=e($versionOferta)?>"
    aria-haspopup="dialog" aria-controls="sga-modal-docente-individual"
    <?=$soloLectura?'disabled':''?>>Editar docente</button>
  <form method="post"><input type="hidden" name="csrf_aula_gestion" value="<?=e($csrfAulaGestion)?>"><input type="hidden" name="accion" value="toggle_oferta"><input type="hidden" name="aula_periodo_id" value="<?=$apId?>"><input type="hidden" name="oferta_id" value="<?=$o['id']?>"><button class="btn btn-sm <?=$o['activo']?'btn-secondary':'btn-success'?>" data-confirm="¿Cambiar el estado de esta asignación?" <?=$soloLectura?'disabled':''?>><?=$o['activo']?'Desactivar':'Activar'?></button></form>
  <form method="post"><input type="hidden" name="csrf_aula_gestion" value="<?=e($csrfAulaGestion)?>"><input type="hidden" name="accion" value="eliminar_oferta"><input type="hidden" name="aula_periodo_id" value="<?=$apId?>"><input type="hidden" name="oferta_id" value="<?=$o['id']?>"><button class="btn btn-sm btn-danger" data-confirm="Solo se eliminará si no tiene notas, asistencia ni configuración. ¿Continuar?" <?=$soloLectura?'disabled':''?>>Eliminar</button></form>
 </div></td>
</tr>
<?php endforeach;?>
</tbody></table></div>
<?php endif;?>
<?php if($historialParametros || (!$modoParametros && $principalParametros)):?>
<details class="card"><summary><strong>Historial de evaluaciones por parámetros</strong></summary><p class="mini-note">Registros anteriores en solo consulta. No se combinan ni se sobrescriben valoraciones.</p><div class="actions">
<?php foreach(array_merge($historialParametros,(!$modoParametros && $principalParametros)?[$principalParametros]:[]) as $h):?><a class="btn btn-secondary" href="<?=e(url('modulos/calificaciones/parametros.php?oferta_id='.$h['id'].'&vista=resumen'))?>"><?=e($h['asignatura'].' · '.$h['valoraciones'].' valoraciones')?></a><?php endforeach;?>
</div></details><?php endif;?>
<div class="mini-note" role="note">Los traslados conservan las calificaciones y asistencias antiguas en el aula original; no trasladan automáticamente esas notas a la nueva asignatura. El administrador debe revisar la equivalencia académica.</div>
<?php $totalActivos=count(array_filter($matriculas,static function($m){return $m['estado']==='activo';})); ?>
<div class="toolbar" style="margin-top:18px;gap:12px;align-items:center">
  <div>
    <h2 class="section-title" style="margin:0 0 4px">Estudiantes matriculados</h2>
    <p class="muted" style="margin:0">Numeración guardada por aula. Ordenar de A a Z usa apellidos y después nombres (solo matrículas activas).</p>
  </div>
  <?php if(!$soloLectura && $totalActivos>0): ?>
  <form method="post"><input type="hidden" name="csrf_aula_gestion" value="<?=e($csrfAulaGestion)?>">
    <input type="hidden" name="accion" value="reordenar_alfabeticamente">
    <input type="hidden" name="aula_periodo_id" value="<?=$apId?>">
    <input type="hidden" name="csrf_reordenar_aula" value="<?=e($_SESSION['csrf_reordenar_aula'])?>">
    <button class="btn btn-primary" type="submit" data-confirm="¿Ordenar todos los estudiantes activos por apellidos y nombres? Se reemplazarán sus números de lista actuales y el nuevo orden quedará guardado en la base de datos.">Ordenar A-Z y guardar</button>
  </form>
  <?php endif; ?>
</div>
<div class="table-wrap"><table class="table table-responsive-cards"><thead><tr><th>No.</th><th>Cédula</th><th>Estudiante</th><th>Estado</th><th>Acciones</th></tr></thead><tbody><?php if(!$matriculas):?><tr><td colspan="5" class="empty">Sin estudiantes.</td></tr><?php endif;?><?php foreach($matriculas as $m):?><tr><td><form method="post" class="actions"><input type="hidden" name="csrf_aula_gestion" value="<?=e($csrfAulaGestion)?>"><input type="hidden" name="accion" value="editar_matricula"><input type="hidden" name="aula_periodo_id" value="<?=$apId?>"><input type="hidden" name="matricula_id" value="<?=$m['matricula_id']?>"><input style="width:75px" type="number" min="1" name="numero_lista" value="<?=e($m['numero_lista']??'')?>"><button class="btn btn-sm btn-secondary">Guardar</button></form></td><td><?=e($m['cedula'])?></td><td><strong><?=e($m['apellidos'].' '.$m['nombres'])?></strong></td><td><span class="badge <?=$m['estado']==='activo'?'good':($m['estado']==='retirado'?'bad':'')?>"><?=e(ucfirst($m['estado']))?></span></td><td><div class="actions"><?php if($m['estado']==='activo'):?>
<?php if($paralelosDestino):?><form method="post" class="actions"><input type="hidden" name="csrf_aula_gestion" value="<?=e($csrfAulaGestion)?>"><input type="hidden" name="accion" value="trasladar"><input type="hidden" name="aula_periodo_id" value="<?=$apId?>"><input type="hidden" name="matricula_id" value="<?=$m['matricula_id']?>"><label class="sr-only" for="destino-<?=$m['matricula_id']?>">Paralelo de destino</label><select id="destino-<?=$m['matricula_id']?>" name="destino_apid" required aria-label="Paralelo de destino" style="min-width:145px;max-width:210px"><option value="">Trasladar a...</option><?php foreach($paralelosDestino as $destino):?><option value="<?=(int)$destino['id']?>"><?=e($destino['nivel'].' '.$destino['nombre'].' '.$destino['paralelo'])?></option><?php endforeach;?></select><button class="btn btn-sm btn-secondary" data-confirm="¿Trasladar a este estudiante? Sus calificaciones y asistencia anteriores permanecerán en la matrícula original para consulta histórica.">Trasladar</button></form><?php endif;?>
<form method="post"><input type="hidden" name="csrf_aula_gestion" value="<?=e($csrfAulaGestion)?>"><input type="hidden" name="accion" value="retirar"><input type="hidden" name="aula_periodo_id" value="<?=$apId?>"><input type="hidden" name="matricula_id" value="<?=$m['matricula_id']?>"><button class="btn btn-sm btn-secondary" data-confirm="¿Retirar al estudiante de este paralelo?">Retirar</button></form><?php else:?><form method="post"><input type="hidden" name="csrf_aula_gestion" value="<?=e($csrfAulaGestion)?>"><input type="hidden" name="accion" value="reactivar"><input type="hidden" name="aula_periodo_id" value="<?=$apId?>"><input type="hidden" name="matricula_id" value="<?=$m['matricula_id']?>"><button class="btn btn-sm btn-success" data-confirm="¿Reactivar esta matrícula?">Reactivar</button></form><?php endif;?><form method="post"><input type="hidden" name="csrf_aula_gestion" value="<?=e($csrfAulaGestion)?>"><input type="hidden" name="accion" value="eliminar_matricula"><input type="hidden" name="aula_periodo_id" value="<?=$apId?>"><input type="hidden" name="matricula_id" value="<?=$m['matricula_id']?>"><button class="btn btn-sm btn-danger" data-confirm="Solo se eliminará si no tiene notas, asistencia ni voto electoral. ¿Continuar?">Eliminar</button></form></div></td></tr><?php endforeach;?></tbody></table></div>

<?php if($soloLectura):?><script>
(function(){document.querySelectorAll('main form[method="post"] input:not([type="hidden"]), main form[method="post"] select, main form[method="post"] button').forEach(function(c){c.disabled=true;});})();
</script><?php endif;?>
<?php require __DIR__.'/../../partials/footer.php';?>
