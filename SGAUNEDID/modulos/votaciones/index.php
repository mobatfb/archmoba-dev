<?php
require_once __DIR__.'/_lib.php';
exigirLogin();
$p=periodoActivo();
if(!$p){$tituloPagina='Votaciones';$subtituloPagina='No existe un periodo académico activo.';require APP_ROOT.'/partials/header.php';echo '<div class="notice">Activa un periodo académico para utilizar el módulo electoral.</div>';require APP_ROOT.'/partials/footer.php';exit;}
if(!esSuperadmin()){
    if(esEstudianteOperativo((int)$p['id'])) redir('modulos/votaciones/votar.php');
    http_response_code(403);die('Este módulo está disponible para el superadministrador y estudiantes habilitados.');
}

$pid=(int)$p['id'];$uid=(int)$_SESSION['usuario_id'];$eleccion=eleccionPeriodo($pid);
if($_SERVER['REQUEST_METHOD']==='POST'){
    validarVotacionCsrf();$accion=(string)($_POST['accion']??'');
    try{
        if($accion==='crear'){
            if($eleccion)throw new RuntimeException('Ya existe un proceso electoral para este periodo académico.');
            $titulo=trim((string)($_POST['titulo']??''));if($titulo==='')$titulo='Elecciones Estudiantiles '.$p['nombre'];
            $stmt=$conexion->prepare("INSERT INTO elecciones(periodo_id,titulo,mensaje,estado,creada_por) VALUES(?,?,?,'configuracion',?)");$msg='Participa responsablemente en el proceso democrático institucional.';$stmt->bind_param('issi',$pid,$titulo,$msg,$uid);$stmt->execute();$eid=(int)$conexion->insert_id;$stmt->close();
            registrarAuditoria('CREATE','Votaciones','eleccion',$eid,'Proceso electoral creado para el periodo '.$p['nombre'].'.',null,null,['periodo_id'=>$pid,'titulo'=>$titulo],'exito',null,null,'advertencia');
            flash('success','Proceso electoral creado. Ahora asigna las aulas por sección y registra los candidatos.');redir('modulos/votaciones/index.php');
        }
        if(!$eleccion)throw new RuntimeException('Primero crea el proceso electoral.');
        $eid=(int)$eleccion['id'];
        if($accion==='configurar'){
            if($eleccion['estado']!=='configuracion')throw new RuntimeException('La configuración general queda bloqueada después de activar la elección.');
            $titulo=trim((string)($_POST['titulo']??''));$mensaje=trim((string)($_POST['mensaje']??''));
            $fi=trim((string)($_POST['fecha_inicio']??''));$ff=trim((string)($_POST['fecha_fin']??''));
            $fi=$fi!==''?str_replace('T',' ',$fi).':00':null;$ff=$ff!==''?str_replace('T',' ',$ff).':00':null;
            if($fi&&$ff&&strtotime($ff)<=strtotime($fi))throw new RuntimeException('La fecha de cierre debe ser posterior a la fecha de inicio.');
            $antes=['titulo'=>$eleccion['titulo'],'mensaje'=>$eleccion['mensaje'],'fecha_inicio'=>$eleccion['fecha_inicio'],'fecha_fin'=>$eleccion['fecha_fin']];
            $stmt=$conexion->prepare('UPDATE elecciones SET titulo=?,mensaje=?,fecha_inicio=?,fecha_fin=? WHERE id=?');$stmt->bind_param('ssssi',$titulo,$mensaje,$fi,$ff,$eid);$stmt->execute();$stmt->close();
            registrarAuditoria('UPDATE','Votaciones','eleccion',$eid,'Configuración del proceso electoral actualizada.',null,$antes,['titulo'=>$titulo,'mensaje'=>$mensaje,'fecha_inicio'=>$fi,'fecha_fin'=>$ff]);
            flash('success','Configuración electoral actualizada.');redir('modulos/votaciones/index.php');
        }
        if($accion==='activar'){
            if($eleccion['estado']!=='configuracion')throw new RuntimeException('La elección ya fue activada o cerrada.');
            if(!empty($eleccion['activada_en']))throw new RuntimeException('Este proceso ya fue activado anteriormente y no puede activarse por segunda vez.');
            $aulas=poblacionEleccion($eid);$cm=0;$cv=0;
            $stmt=$conexion->prepare("SELECT seccion,COUNT(*) c FROM eleccion_candidatos WHERE eleccion_id=? AND activo=1 GROUP BY seccion");$stmt->bind_param('i',$eid);$stmt->execute();$rs=$stmt->get_result();while($r=$rs->fetch_assoc()){if($r['seccion']==='matutina')$cm=(int)$r['c'];if($r['seccion']==='vespertina')$cv=(int)$r['c'];}$stmt->close();
            if($aulas<1)throw new RuntimeException('No hay estudiantes habilitados. Asigna al menos un aula a una sección.');
            if(poblacionEleccion($eid,'matutina')>0&&$cm<1)throw new RuntimeException('La sección Matutina tiene estudiantes, pero no tiene candidatos.');
            if(poblacionEleccion($eid,'vespertina')>0&&$cv<1)throw new RuntimeException('La sección Vespertina tiene estudiantes, pero no tiene candidatos.');
            $stmt=$conexion->prepare("UPDATE elecciones SET estado='activa',activada_en=NOW() WHERE id=? AND estado='configuracion' AND activada_en IS NULL");$stmt->bind_param('i',$eid);$stmt->execute();if($stmt->affected_rows!==1){$stmt->close();throw new RuntimeException('No fue posible activar el proceso.');}$stmt->close();
            registrarAuditoria('ACTIVATE','Votaciones','eleccion',$eid,'Proceso electoral activado por única vez para el periodo '.$p['nombre'].'.',null,['estado'=>'configuracion'],['estado'=>'activa'],'exito',null,null,'critica');
            flash('success','Elección activada. Los estudiantes habilitados ya pueden votar.');redir('modulos/votaciones/index.php');
        }
        if($accion==='cerrar'){
            if($eleccion['estado']!=='activa')throw new RuntimeException('Solo una elección activa puede cerrarse.');
            $stmt=$conexion->prepare("UPDATE elecciones SET estado='cerrada',cerrada_en=NOW() WHERE id=? AND estado='activa'");$stmt->bind_param('i',$eid);$stmt->execute();$stmt->close();
            registrarAuditoria('CLOSE','Votaciones','eleccion',$eid,'Proceso electoral cerrado.',null,['estado'=>'activa'],['estado'=>'cerrada'],'exito',null,null,'critica');
            flash('success','Proceso electoral cerrado. Ya no se admitirán más votos.');redir('modulos/votaciones/index.php');
        }
        if($accion==='eliminar'){
            if($eleccion['estado']!=='configuracion')throw new RuntimeException('Solo puede eliminarse una elección que todavía está en configuración.');
            $stmt=$conexion->prepare('SELECT COUNT(*) c FROM eleccion_votos WHERE eleccion_id=?');$stmt->bind_param('i',$eid);$stmt->execute();$votos=(int)$stmt->get_result()->fetch_assoc()['c'];$stmt->close();if($votos>0)throw new RuntimeException('La elección ya tiene votos y no puede eliminarse.');
            $stmt=$conexion->prepare('SELECT foto FROM eleccion_candidatos WHERE eleccion_id=? AND foto IS NOT NULL');$stmt->bind_param('i',$eid);$stmt->execute();$fotos=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
            $antes=$eleccion;$stmt=$conexion->prepare('DELETE FROM elecciones WHERE id=?');$stmt->bind_param('i',$eid);$stmt->execute();$stmt->close();foreach($fotos as $f){if(!empty($f['foto'])){$ruta=APP_ROOT.'/assets/uploads/votaciones/'.basename($f['foto']);if(is_file($ruta))@unlink($ruta);}}
            registrarAuditoria('DELETE','Votaciones','eleccion',$eid,'Proceso electoral en configuración eliminado.',null,$antes,null,'exito',null,null,'critica');flash('success','Proceso electoral eliminado.');redir('modulos/votaciones/index.php');
        }
    }catch(Throwable $e){flash('error',$e->getMessage());redir('modulos/votaciones/index.php');}
}

$eleccion=eleccionPeriodo($pid);$mat=$ves=$vMat=$vVes=0;$candidatos=[];
if($eleccion){$eid=(int)$eleccion['id'];$mat=poblacionEleccion($eid,'matutina');$ves=poblacionEleccion($eid,'vespertina');$vMat=votosEleccion($eid,'matutina');$vVes=votosEleccion($eid,'vespertina');$stmt=$conexion->prepare('SELECT seccion,COUNT(*) c FROM eleccion_candidatos WHERE eleccion_id=? AND activo=1 GROUP BY seccion');$stmt->bind_param('i',$eid);$stmt->execute();$candidatos=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();}
$cc=['matutina'=>0,'vespertina'=>0];foreach($candidatos as $c)$cc[$c['seccion']]=(int)$c['c'];
$tituloPagina='Votaciones';$subtituloPagina='Proceso electoral estudiantil del periodo '.$p['nombre'].'.';require APP_ROOT.'/partials/header.php';
?>
<?php if(!$eleccion):?>
<div class="card" style="max-width:760px"><h2>Crear proceso electoral anual</h2><p class="muted">El periodo <strong><?=e($p['nombre'])?></strong> todavía no tiene elecciones. Solo puede existir un proceso electoral por periodo académico.</p><form method="post" class="form-grid cols-2"><input type="hidden" name="csrf" value="<?=e(votacionCsrf())?>"><input type="hidden" name="accion" value="crear"><label>Título<input name="titulo" value="Elecciones Estudiantiles <?=e($p['nombre'])?>"></label><div class="form-actions"><button class="btn btn-primary" type="submit">Crear proceso electoral</button></div></form></div>
<?php else:?>
<div class="grid cols-4">
 <div class="card metric"><span>Estado</span><strong style="font-size:22px"><?=e(strtoupper($eleccion['estado']))?></strong></div>
 <div class="card metric"><span>Población matutina</span><strong><?=$mat?></strong><small class="muted"><?=$vMat?> votos</small></div>
 <div class="card metric"><span>Población vespertina</span><strong><?=$ves?></strong><small class="muted"><?=$vVes?> votos</small></div>
 <div class="card metric"><span>Participación total</span><strong><?=($mat+$ves)>0?number_format((($vMat+$vVes)/($mat+$ves))*100,1):'0.0'?>%</strong><small class="muted"><?=($vMat+$vVes)?> de <?=($mat+$ves)?></small></div>
</div>
<div class="toolbar" style="margin-top:18px"><div class="actions"><a class="btn btn-primary" href="<?=e(url('modulos/votaciones/secciones.php'))?>">Aulas y secciones</a><a class="btn btn-secondary" href="<?=e(url('modulos/votaciones/candidatos.php'))?>">Candidatos</a><a class="btn btn-success" href="<?=e(url('modulos/votaciones/resultados.php'))?>">Resultados</a></div></div>
<div class="grid cols-2">
 <div class="card"><h2>Configuración</h2><form method="post" class="form-grid cols-2"><input type="hidden" name="csrf" value="<?=e(votacionCsrf())?>"><input type="hidden" name="accion" value="configurar"><label style="grid-column:1/-1">Título<input name="titulo" value="<?=e($eleccion['titulo'])?>" <?=$eleccion['estado']!=='configuracion'?'disabled':''?>></label><label>Inicio<input type="datetime-local" name="fecha_inicio" value="<?=e($eleccion['fecha_inicio']?date('Y-m-d\TH:i',strtotime($eleccion['fecha_inicio'])):'')?>" <?=$eleccion['estado']!=='configuracion'?'disabled':''?>></label><label>Cierre<input type="datetime-local" name="fecha_fin" value="<?=e($eleccion['fecha_fin']?date('Y-m-d\TH:i',strtotime($eleccion['fecha_fin'])):'')?>" <?=$eleccion['estado']!=='configuracion'?'disabled':''?>></label><label style="grid-column:1/-1">Mensaje<textarea name="mensaje" rows="3" <?=$eleccion['estado']!=='configuracion'?'disabled':''?>><?=e($eleccion['mensaje'])?></textarea></label><?php if($eleccion['estado']==='configuracion'):?><div class="form-actions"><button class="btn btn-secondary" type="submit">Guardar configuración</button></div><?php endif;?></form></div>
 <div class="card"><h2>Control del proceso</h2><p><span class="badge"><?=e($p['nombre'])?></span></p><p class="muted">Candidatos: <?=$cc['matutina']?> matutina · <?=$cc['vespertina']?> vespertina.</p><?php if($eleccion['estado']==='configuracion'):?><div class="notice">Antes de activar, asigna las aulas a Matutina/Vespertina y registra candidatos para las secciones que tengan población. La activación solo puede realizarse una vez.</div><div class="actions"><form method="post" onsubmit="return confirm('¿Activar definitivamente las elecciones? Esta acción solo puede hacerse una vez para este periodo.');"><input type="hidden" name="csrf" value="<?=e(votacionCsrf())?>"><input type="hidden" name="accion" value="activar"><button class="btn btn-success" type="submit">Activar elecciones</button></form><form method="post"><input type="hidden" name="csrf" value="<?=e(votacionCsrf())?>"><input type="hidden" name="accion" value="eliminar"><button class="btn btn-danger" type="submit" data-confirm="¿Eliminar este proceso electoral y su configuración?">Eliminar proceso</button></form></div><?php elseif($eleccion['estado']==='activa'):?><div class="alert success">Elección activa desde <?=e($eleccion['activada_en'])?>.</div><form method="post" onsubmit="return confirm('¿Cerrar las elecciones? Después de cerrar no podrán emitirse más votos.');"><input type="hidden" name="csrf" value="<?=e(votacionCsrf())?>"><input type="hidden" name="accion" value="cerrar"><button class="btn btn-danger" type="submit">Cerrar elecciones</button></form><?php else:?><div class="alert info">Proceso cerrado<?=!empty($eleccion['cerrada_en'])?' el '.e($eleccion['cerrada_en']):''?>. Los resultados quedan disponibles para consulta.</div><?php endif;?></div>
</div>
<?php endif;?>
<?php require APP_ROOT.'/partials/footer.php';?>
