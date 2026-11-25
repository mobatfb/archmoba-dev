<?php
require_once __DIR__.'/_lib.php';
exigirSuperadmin();$p=periodoActivo();if(!$p)redir('modulos/votaciones/index.php');$e=eleccionPeriodo((int)$p['id']);if(!$e){flash('error','Primero crea el proceso electoral.');redir('modulos/votaciones/index.php');}$eid=(int)$e['id'];
if($_SERVER['REQUEST_METHOD']==='POST'){
 validarVotacionCsrf();
 if($e['estado']!=='configuracion'){flash('error','Las secciones quedan bloqueadas después de activar las elecciones.');redir('modulos/votaciones/secciones.php');}
 $grupo=auditoriaGrupo();$conexion->begin_transaction();
 try{
   $stmt=$conexion->prepare("SELECT ap.id,a.nivel,a.nombre,a.paralelo,COALESCE(ea.seccion,'') seccion FROM aulas_periodo ap JOIN aulas a ON a.id=ap.aula_id LEFT JOIN eleccion_aulas ea ON ea.aula_periodo_id=ap.id AND ea.eleccion_id=? WHERE ap.periodo_id=? AND ap.activo=1");$pid=(int)$p['id'];$stmt->bind_param('ii',$eid,$pid);$stmt->execute();$rows=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
   foreach($rows as $r){$apid=(int)$r['id'];$nuevo=(string)($_POST['seccion'][$apid]??'');if(!in_array($nuevo,['matutina','vespertina'],true))$nuevo='';$antes=(string)$r['seccion'];if($antes===$nuevo)continue;
     if($nuevo===''){$st=$conexion->prepare('DELETE FROM eleccion_aulas WHERE eleccion_id=? AND aula_periodo_id=?');$st->bind_param('ii',$eid,$apid);$st->execute();$st->close();}
     else{$st=$conexion->prepare("INSERT INTO eleccion_aulas(eleccion_id,aula_periodo_id,seccion) VALUES(?,?,?) ON DUPLICATE KEY UPDATE seccion=VALUES(seccion)");$st->bind_param('iis',$eid,$apid,$nuevo);$st->execute();$st->close();}
     registrarAuditoria($antes===''?'CREATE':($nuevo===''?'DELETE':'UPDATE'),'Votaciones','eleccion_aula',$apid,'Asignación electoral del aula '.$r['nivel'].' · '.$r['nombre'].' '.$r['paralelo'].' actualizada.',null,['seccion'=>$antes?:null],['seccion'=>$nuevo?:null],'exito',null,$grupo,'advertencia');
   }
   $conexion->commit();flash('success','Distribución Matutina/Vespertina guardada. La población electoral se actualizó automáticamente según las matrículas activas.');
 }catch(Throwable $ex){$conexion->rollback();flash('error','No se pudo guardar la distribución: '.$ex->getMessage());}
 redir('modulos/votaciones/secciones.php');
}
$pid=(int)$p['id'];$stmt=$conexion->prepare("SELECT ap.id,a.nivel,a.nombre,a.paralelo,COALESCE(ea.seccion,'') seccion,(SELECT COUNT(*) FROM matriculas m WHERE m.aula_periodo_id=ap.id AND m.estado='activo') estudiantes FROM aulas_periodo ap JOIN aulas a ON a.id=ap.aula_id LEFT JOIN eleccion_aulas ea ON ea.aula_periodo_id=ap.id AND ea.eleccion_id=? WHERE ap.periodo_id=? AND ap.activo=1 ORDER BY a.nivel,a.nombre,a.paralelo");$stmt->bind_param('ii',$eid,$pid);$stmt->execute();$aulas=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
$tituloPagina='Aulas y secciones electorales';$subtituloPagina='Define qué paralelos pertenecen a la sección Matutina o Vespertina. Los estudiantes se toman automáticamente de las matrículas activas.';require APP_ROOT.'/partials/header.php';
?>
<div class="toolbar"><a class="btn btn-secondary" href="<?=e(url('modulos/votaciones/index.php'))?>">← Votaciones</a><div class="stat-row"><span class="tag">Matutina: <?=poblacionEleccion($eid,'matutina')?> estudiantes</span><span class="tag">Vespertina: <?=poblacionEleccion($eid,'vespertina')?> estudiantes</span></div></div>
<?php if($e['estado']!=='configuracion'):?><div class="alert info">La elección ya fue activada. La distribución de aulas está bloqueada para conservar el padrón electoral del proceso.</div><?php endif;?>
<form method="post"><input type="hidden" name="csrf" value="<?=e(votacionCsrf())?>"><div class="table-wrap"><table class="table table-responsive-cards"><thead><tr><th>Aula / paralelo</th><th>Matriculados activos</th><th>Sección electoral</th></tr></thead><tbody>
<?php foreach($aulas as $a):?><tr><td><strong><?=e($a['nivel'].' · '.$a['nombre'].' '.$a['paralelo'])?></strong></td><td><?= (int)$a['estudiantes']?></td><td><select name="seccion[<?=(int)$a['id']?>]" <?=$e['estado']!=='configuracion'?'disabled':''?>><option value="">No participa</option><option value="matutina" <?=$a['seccion']==='matutina'?'selected':''?>>Matutina</option><option value="vespertina" <?=$a['seccion']==='vespertina'?'selected':''?>>Vespertina</option></select></td></tr><?php endforeach;?>
<?php if(!$aulas):?><tr><td colspan="3" class="empty">No existen aulas habilitadas en el periodo activo.</td></tr><?php endif;?>
</tbody></table></div><?php if($e['estado']==='configuracion'&&$aulas):?><div class="savebar"><span class="muted">Los estudiantes no se copian a otra tabla: el padrón se obtiene de estas aulas y sus matrículas activas.</span><button class="btn btn-primary" type="submit">Guardar secciones</button></div><?php endif;?></form>
<?php require APP_ROOT.'/partials/footer.php';?>
