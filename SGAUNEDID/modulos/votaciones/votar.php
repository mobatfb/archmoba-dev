<?php
require_once __DIR__.'/_lib.php';
exigirLogin();$p=periodoActivo();if(!$p){http_response_code(403);die('No existe un periodo académico activo.');}$pid=(int)$p['id'];if(!esEstudianteOperativo($pid)){http_response_code(403);die('Solo los estudiantes matriculados pueden acceder a la votación.');}
$uid=(int)$_SESSION['usuario_id'];$e=eleccionPeriodo($pid);
if($_SERVER['REQUEST_METHOD']==='POST'){
 validarVotacionCsrf();$enTransaccion=false;
 try{
   if(!$e)throw new RuntimeException('No existe un proceso electoral para este periodo.');if(!eleccionEstaAbierta($e))throw new RuntimeException('La votación no está abierta en este momento.');
   $eid=(int)$e['id'];$elector=electorEleccion($eid,$uid);if(!$elector)throw new RuntimeException('Tu paralelo no está habilitado en este proceso electoral.');
   $cid=(int)($_POST['candidato_id']??0);if($cid<1)throw new RuntimeException('Selecciona un candidato.');
   $stmt=$conexion->prepare('SELECT id,nombre,seccion FROM eleccion_candidatos WHERE id=? AND eleccion_id=? AND activo=1 LIMIT 1');$stmt->bind_param('ii',$cid,$eid);$stmt->execute();$cand=$stmt->get_result()->fetch_assoc();$stmt->close();if(!$cand||$cand['seccion']!==$elector['seccion'])throw new RuntimeException('El candidato seleccionado no corresponde a tu sección electoral.');
   $conexion->begin_transaction();$enTransaccion=true;
   $stmt=$conexion->prepare('SELECT id FROM eleccion_votos WHERE eleccion_id=? AND estudiante_id=? LIMIT 1 FOR UPDATE');$stmt->bind_param('ii',$eid,$uid);$stmt->execute();$ya=$stmt->get_result()->fetch_assoc();$stmt->close();if($ya){$conexion->rollback();flash('info','Tu voto ya había sido registrado. Cada estudiante puede votar una sola vez.');redir('modulos/votaciones/votar.php');}
   $apid=(int)$elector['aula_periodo_id'];$sec=$elector['seccion'];$stmt=$conexion->prepare('INSERT INTO eleccion_votos(eleccion_id,estudiante_id,candidato_id,aula_periodo_id,seccion) VALUES(?,?,?,?,?)');$stmt->bind_param('iiiis',$eid,$uid,$cid,$apid,$sec);$stmt->execute();$vid=(int)$conexion->insert_id;$stmt->close();$conexion->commit();$enTransaccion=false;
   // La auditoría registra que el estudiante participó, pero deliberadamente no almacena el candidato elegido en el detalle.
   registrarAuditoria('VOTE','Votaciones','eleccion_voto',$vid,'Estudiante emitió su voto en la sección '.$sec.'.',$uid,null,['eleccion_id'=>$eid,'seccion'=>$sec],'exito',null,null,'advertencia');
   flash('success','Tu voto fue registrado correctamente. Gracias por participar.');redir('modulos/votaciones/votar.php');
 }catch(Throwable $ex){if($enTransaccion){try{$conexion->rollback();}catch(Throwable $ignore){}}flash('error',$ex->getMessage());redir('modulos/votaciones/votar.php');}
}
$elector=$e?electorEleccion((int)$e['id'],$uid):null;$yaVoto=false;$candidatos=[];
if($e){$eid=(int)$e['id'];$stmt=$conexion->prepare('SELECT 1 FROM eleccion_votos WHERE eleccion_id=? AND estudiante_id=? LIMIT 1');$stmt->bind_param('ii',$eid,$uid);$stmt->execute();$yaVoto=(bool)$stmt->get_result()->fetch_row();$stmt->close();if($elector){$sec=$elector['seccion'];$stmt=$conexion->prepare('SELECT id,nombre,foto,propuesta,seccion FROM eleccion_candidatos WHERE eleccion_id=? AND seccion=? AND activo=1 ORDER BY nombre');$stmt->bind_param('is',$eid,$sec);$stmt->execute();$candidatos=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();}}
$tituloPagina='Votaciones estudiantiles';$subtituloPagina=$e?$e['titulo'].' · '.$p['nombre']:'Proceso electoral del periodo '.$p['nombre'];require APP_ROOT.'/partials/header.php';
?>
<?php if(!$e):?><div class="card empty"><h3>No existe un proceso electoral configurado para este periodo.</h3></div>
<?php elseif(!$elector):?><div class="notice">Tu cuenta está matriculada, pero tu aula no fue asignada a la población electoral Matutina o Vespertina. Consulta con administración.</div>
<?php elseif($yaVoto):?><div class="vote-thanks"><div class="vote-check">✓</div><h2>Tu voto ya fue registrado</h2><p>Gracias por participar en las elecciones estudiantiles de la UNEDID.</p><span class="badge"><?=e(ucfirst($elector['seccion']))?></span></div>
<?php elseif(!eleccionEstaAbierta($e)):?><div class="card"><h2>Proceso no disponible para votar</h2><p class="muted">Estado: <strong><?=e(strtoupper($e['estado']))?></strong>.</p><?php if($e['estado']==='activa'&&!empty($e['fecha_inicio'])&&time()<strtotime($e['fecha_inicio'])):?><div class="notice">La votación se habilitará el <?=e(date('d/m/Y H:i',strtotime($e['fecha_inicio'])))?>.</div><?php elseif($e['estado']==='activa'&&!empty($e['fecha_fin'])&&time()>strtotime($e['fecha_fin'])):?><div class="notice">El horario de votación finalizó el <?=e(date('d/m/Y H:i',strtotime($e['fecha_fin'])))?>.</div><?php else:?><div class="notice">La administración todavía no ha habilitado la votación o el proceso ya fue cerrado.</div><?php endif;?></div>
<?php else:?>
<div class="vote-hero"><div><span class="badge"><?=e(ucfirst($elector['seccion']))?></span><h2><?=e($e['titulo'])?></h2><p><?=e($e['mensaje'])?></p><small><?=e($elector['nivel'].' · '.$elector['aula'].' '.$elector['paralelo'])?></small></div></div>
<form method="post" id="formVoto"><input type="hidden" name="csrf" value="<?=e(votacionCsrf())?>"><div class="candidate-vote-grid">
<?php foreach($candidatos as $c):?><label class="candidate-vote-card"><input type="radio" name="candidato_id" value="<?=(int)$c['id']?>" required><?php $fu=fotoCandidatoUrl($c['foto']);?><?php if($fu):?><img src="<?=e($fu)?>" alt="Fotografía de <?=e($c['nombre'])?>"><?php else:?><div class="candidate-placeholder">Sin foto</div><?php endif;?><div class="candidate-vote-copy"><h3><?=e(strtoupper($c['nombre']))?></h3><p><?=e($c['propuesta'])?></p><span class="candidate-select">Seleccionar</span></div></label><?php endforeach;?>
<?php if(!$candidatos):?><div class="card empty">No existen candidatos habilitados para tu sección.</div><?php endif;?></div>
<?php if($candidatos):?><div class="vote-submit"><button class="btn btn-primary" type="submit" onclick="return confirm('¿Confirmas tu voto? Una vez registrado no podrás cambiarlo.');">Registrar mi voto</button><p class="mini-note">El voto solo puede emitirse una vez durante este periodo académico.</p></div><?php endif;?></form>
<?php endif;?>
<?php require APP_ROOT.'/partials/footer.php';?>
